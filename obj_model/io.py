""" Reading/writing schema objects to/from files

* Comma separated values (.csv)
* Excel (.xlsx)
* Tab separated values (.tsv)

:Author: Jonathan Karr <karr@mssm.edu>
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

import collections
import copy
from itertools import chain, compress
from natsort import natsorted, ns
from os.path import basename, dirname, splitext
from warnings import warn
from obj_model import utils
from obj_model.core import (Model, Attribute, RelatedAttribute, Validator, TabularOrientation,
                                  InvalidObject, excel_col_name,
                                  InvalidAttribute, ObjModelWarning)
from wc_utils.util.list import transpose
from wc_utils.workbook.io import (get_writer, get_reader, WorkbookStyle, WorksheetStyle,
                                  Writer as BaseWriter, Reader as BaseReader,
                                  convert as base_convert)
from wc_utils.util.misc import quote
from wc_utils.util.string import indent_forest


class Writer(object):
    """ Write model objects to file(s) """

    def run(self, path, objects, models, get_related=True,
        title=None, description=None, keywords=None, version=None, language=None, creator=None):
        """ Write a list of model classes to an Excel file, with one worksheet for each model, or to
            a set of .csv or .tsv files, with one file for each model.

        Args:
            path (:obj:`str`): path to write file(s)
            objects (:obj:`list`): list of objects
            models (:obj:`list` of `Model`): models in the order that they should
                appear as worksheets; all models which are not in `models` will
                follow in alphabetical order
            title (:obj:`str`, optional): title
            description (:obj:`str`, optional): description
            keywords (:obj:`str`, optional): keywords
            version (:obj:`str`, optional): version
            language (:obj:`str`, optional): language
            creator (:obj:`str`, optional): creator
        """

        sheet_names = []
        for model in models:
            if model.Meta.tabular_orientation == TabularOrientation.row:
                sheet_names.append(model.Meta.verbose_name_plural)
            else:
                sheet_names.append(model.Meta.verbose_name)
        ambiguous_sheet_names = get_ambiguous_sheet_names(sheet_names, models)
        if ambiguous_sheet_names:
            msg = 'The following sheets will not be able to be unambiguously mapped to models:'
            for sheet_name, models in ambiguous_sheet_names.items():
                msg += '\n  {}: {}'.format(sheet_name, ', '.join(model.__name__ for model in models))
            warn(msg, IoWarning)

        # get related objects
        more_objects = []
        if get_related:
            for obj in objects:
                more_objects.extend(obj.get_related())

        # clean objects
        all_objects = list(set(objects + more_objects))
        error = Validator().run(all_objects)

        if error:
            warn('Some data will not be written because objects are not valid:\n  {}'.format(
                str(error).replace('\n', '\n  ').rstrip()), IoWarning)

        # group objects by class
        grouped_objects = {}
        for obj in all_objects:
            if obj.__class__ not in grouped_objects:
                grouped_objects[obj.__class__] = []
            if obj not in grouped_objects[obj.__class__]:
                grouped_objects[obj.__class__].append(obj)

        # check that models are serializble
        for cls in grouped_objects.keys():
            if not cls.is_serializable():
                raise ValueError('Class {}.{} cannot be serialized'.format(cls.__module__, cls.__name__))

        # get neglected models
        unordered_models = natsorted(set(grouped_objects.keys()).difference(set(models)),
                                     lambda model: model.Meta.verbose_name, alg=ns.IGNORECASE)

        # add sheets
        _, ext = splitext(path)
        writer_cls = get_writer(ext)
        writer = writer_cls(path,
                            title=title, description=description, keywords=keywords,
                            version=version, language=language, creator=creator)
        writer.initialize_workbook()

        for model in chain(models, unordered_models):
            if model.Meta.tabular_orientation == TabularOrientation.inline:
                continue

            if model in grouped_objects:
                objects = grouped_objects[model]
            else:
                objects = []

            self.write_model(writer, model, objects)

        writer.finalize_workbook()

    def write_model(self, writer, model, objects):
        """ Write a list of model objects to a file

        Args:
            writer (:obj:`BaseWriter`): io writer
            model (:obj:`class`): model
            objects (:obj:`list` of `Model`): list of instances of `model`
        """

        # attribute order
        attributes = [model.Meta.attributes[attr_name] for attr_name in model.Meta.attribute_order]

        # column labels
        headings = [[attr.verbose_name for attr in attributes]]

        header_map = collections.defaultdict(list)
        for heading in headings[0]:
            l = heading.lower()
            header_map[l].append(heading)
        duplicate_headers = list(filter(lambda x: 1 < len(x), header_map.values()))
        if duplicate_headers:
            errors = []
            for dupes in duplicate_headers:
                str = ', '.join(map(lambda s: "'{}'".format(s), dupes))
                warn('Duplicate, case insensitive, header fields: {}'.format(str), IoWarning)

        # objects
        model.sort(objects)

        data = []
        for obj in objects:
            obj_data = []
            for attr in attributes:
                obj_data.append(attr.serialize(getattr(obj, attr.name)))
            data.append(obj_data)

        # transpose data for column orientation
        style = self.create_worksheet_style(model)
        if model.Meta.tabular_orientation == TabularOrientation.row:
            self.write_sheet(writer,
                             sheet_name=model.Meta.verbose_name_plural,
                             data=data,
                             column_headings=headings,
                             style=style,
                             )
        else:
            self.write_sheet(writer,
                             sheet_name=model.Meta.verbose_name,
                             data=transpose(data),
                             row_headings=headings,
                             style=style,
                             )

    def write_sheet(self, writer, sheet_name, data, row_headings=None, column_headings=None, style=None):
        """ Write data to sheet

        Args:
            writer (:obj:`BaseWriter`): io writer
            sheet_name (:obj:`str`): sheet name
            data (:obj:`list` of `list` of `object`): list of list of cell values
            row_headings (:obj:`list` of `list` of `str`, optional): list of list of row headings
            column_headings (:obj:`list` of `list` of `str`, optional): list of list of column headings
            style (:obj:`WorksheetStyle`, optional): worksheet style
        """
        row_headings = row_headings or []
        column_headings = copy.deepcopy(column_headings) or []

        # merge data, headings
        for i_row, row_heading in enumerate(transpose(row_headings)):
            if i_row < len(data):
                row = data[i_row]
            else:
                row = []
                data.append(row)

            for val in row_heading:
                row.insert(0, val)

        for i_row in range(len(row_headings)):
            for column_heading in column_headings:
                column_heading.insert(0, None)

        content = column_headings + data

        # write content to worksheet
        writer.write_worksheet(sheet_name, content, style=style)

    @staticmethod
    def create_worksheet_style(model):
        """ Create worksheet style for model

        Args:
            model (:obj:`class`): model class

        Returns:
            :obj:`WorksheetStyle`: worksheet style
        """
        style = WorksheetStyle(
            head_row_font_bold=True,
            head_row_fill_pattern='solid',
            head_row_fill_fgcolor='CCCCCC',
            row_height=15,
        )

        if model.Meta.tabular_orientation == TabularOrientation.row:
            style.head_rows = 1
            style.head_columns = model.Meta.frozen_columns
        else:
            style.head_rows = model.Meta.frozen_columns
            style.head_columns = 1

        return style


class Reader(object):
    """ Read model objects from file(s) """

    def run(self, path, models, ignore_other_sheets=False, ignore_missing_attributes=False, ignore_extra_attributes=False):
        """ Read a list of model objects from file(s) and validate them

        File(s) may be a single Excel workbook with multiple worksheets or a set of delimeter
        separated files encoded by a single path with a glob pattern.

        Args:
            path (:obj:`str`): path to file(s)
            models (:obj:`list` of :obj:`Model`): list of `Model` classes to read
            ignore_other_sheets (:obj:`boolean`, optional): if true and all `models` are found, ignore
                other worksheets or files
            ignore_missing_attributes (:obj:`boolean`, optional): if false, report an error if a
                worksheet/file doesn't contain all of attributes in a model in `models`
            ignore_extra_attributes (:obj:`boolean`, optional): if set, do not report errors if
                attributes in the data are not in the model

        Returns:
            :obj:`dict`: model objects grouped by `Model` class

        Raises:
            :obj:`ValueError`: if

                * Sheets cannot be unambiguously mapped to models
                * The file(s) indicated by `path` contains extra sheets that don't correspond to one
                of `models` and `ignore_other_sheets` is True
                * Some models are not serializable
                * The data contains parsing errors found by `read_model`
        """

        # initialize reader
        _, ext = splitext(path)
        reader_cls = get_reader(ext)
        reader = reader_cls(path)

        # initialize reading
        workbook = reader.initialize_workbook()

        # check that sheets can be unambiguously mapped to models
        sheet_names = reader.get_sheet_names()
        ambiguous_sheet_names = get_ambiguous_sheet_names(sheet_names, models)
        if ambiguous_sheet_names:
            msg = 'The following sheets cannot be unambiguously mapped to models:'
            for sheet_name, models in ambiguous_sheet_names.items():
                msg += '\n  {}: {}'.format(sheet_name, ', '.join(model.__name__ for model in models))
            raise ValueError(msg)

        # check that models are defined for each worksheet
        used_sheet_names = dict()
        for model in models:
            model_sheet_name = get_model_sheet_name(sheet_names, model)
            if model_sheet_name:
                used_sheet_names[model_sheet_name] = model

        extra_sheet_names = set(reader.get_sheet_names()).difference(set(used_sheet_names.keys()))
        if extra_sheet_names and not ignore_other_sheets:
            raise ValueError("No matching models for worksheets/files {} / {}".format(
                basename(path), "', '".join(sorted(extra_sheet_names))))

        # check that models are valid
        for model in models:
            model.validate_related_attributes()

        # check that models are serializable
        for model in models:
            if not model.is_serializable():
                raise ValueError('Class {}.{} cannot be serialized'.format(model.__module__, model.__name__))

        # read objects
        attributes = {}
        data = {}
        errors = {}
        objects = {}
        for model in models:
            model_attributes, model_data, model_errors, model_objects = self.read_model(reader, model,
                ignore_missing_attributes=ignore_missing_attributes,
                ignore_extra_attributes=ignore_extra_attributes)
            if model_attributes:
                attributes[model] = model_attributes
            if model_data:
                data[model] = model_data
            if model_errors:
                errors[model] = model_errors
            if model_objects:
                objects[model] = model_objects

        if errors:
            forest = ["The model cannot be loaded because '{}' contains error(s):".format(basename(path))]
            for model, model_errors in errors.items():
                forest.append([quote(model.__name__)])
                forest.append([model_errors])
            raise ValueError(indent_forest(forest))

        # link objects
        objects_by_primary_attribute = {}
        for model, objects_model in objects.items():
            objects_by_primary_attribute[model] = {obj.get_primary_attribute(): obj for obj in objects_model}

        errors = {}
        for model, objects_model in objects.items():
            model_errors = self.link_model(model, attributes[model], data[model], objects_model,
                                           objects_by_primary_attribute)
            if model_errors:
                errors[model] = model_errors

        if errors:
            forest = ["The model cannot be loaded because '{}' contains error(s):".format(basename(path))]
            for model, model_errors in errors.items():
                forest.append([quote(model.__name__)])
                forest.append([model_errors])
            raise ValueError(indent_forest(forest))

        # convert to sets
        for model in models:
            if model in objects:
                objects[model] = objects[model]
            else:
                objects[model] = []

        for model, model_objects in objects_by_primary_attribute.items():
            if model not in objects:
                objects[model] = []
            objects[model] = list(set(objects[model] + list(model_objects.values())))

        # validate
        all_objects = []
        for model in models:
            all_objects.extend(objects[model])

        errors = Validator().validate(all_objects)
        if errors:
            raise ValueError(
                indent_forest(['The model cannot be loaded because it fails to validate:', [errors]]))

        # return
        return objects

    def read_model(self, reader, model, ignore_missing_attributes=False, ignore_extra_attributes=False):
        """ Instantiate a list of objects from data in a table in a file

        Args:
            reader (:obj:`BaseReader`): reader
            model (:obj:`class`): the model describing the objects' schema
            ignore_missing_attributes (:obj:`boolean`, optional): if false, report an error if the worksheet/files
                don't have all of attributes in the model
            ignore_extra_attributes (:obj:`boolean`, optional): if set, do not report errors if attributes
                in the data are not in the model

        Returns:
            :obj:`tuple` of
                `list` of `Attribute`,
                `list` of `list` of `object`,
                `list` of `str`,
                `list` of `Model`: tuple of
                * attribute order of `data`
                * a two-dimensional nested list of object data
                * a list of parsing errors
                * constructed model objects
        """
        _, ext = splitext(reader.path)
        sheet_name = get_model_sheet_name(reader.get_sheet_names(), model)
        if not sheet_name:
            return ([], [], None, [])

        # get worksheet
        if model.Meta.tabular_orientation == TabularOrientation.row:
            data, _, headings = self.read_sheet(reader, sheet_name, num_column_heading_rows=1)
        else:
            data, headings, _ = self.read_sheet(reader, sheet_name, num_row_heading_columns=1)
            data = transpose(data)
        headings = headings[0]

        # prohibit duplicate headers
        header_map = collections.defaultdict(list)
        for heading in headings:
            if heading is None:
                continue
            l = heading.lower()
            header_map[l].append(heading)
        duplicate_headers = list(filter(lambda x: 1 < len(x), header_map.values()))
        if duplicate_headers:
            errors = []
            for dupes in duplicate_headers:
                str = ', '.join(map(lambda s: "'{}'".format(s), dupes))
                errors.append("{}:'{}': Duplicate, case insensitive, header fields: {}".format(
                    basename(reader.path), sheet_name, str))
            return ([], [], errors, [])

        # acquire attributes by header order
        attributes = []
        good_columns = []
        errors = []
        for idx, heading in enumerate(headings, start=1):
            attr = utils.get_attribute_by_name(model, heading, case_insensitive=True) or \
                utils.get_attribute_by_verbose_name(model, heading, case_insensitive=True)

            if attr is not None:
                attributes.append(attr)
            if attr is None and not ignore_extra_attributes:
                row, col, hdr_entries = header_row_col_names(idx, ext, model.Meta.tabular_orientation)
                if heading is None or heading == '':
                    errors.append("Empty header field in row {}, col {} - delete empty {}(s)".format(
                        row, col, hdr_entries))
                else:
                    errors.append("Header '{}' in row {}, col {} does not match any attribute".format(
                        heading, row, col))
            if ignore_extra_attributes:
                if attr is None:
                    good_columns.append(0)
                else:
                    good_columns.append(1)

        if errors:
            return ([], [], errors, [])

        # check that all attributes have column headings
        # todo
        if not ignore_missing_attributes:
            pass

        # save model location in file
        attribute_seq = []
        for heading in headings:
            attr = utils.get_attribute_by_name(model, heading, case_insensitive=True) or \
                utils.get_attribute_by_verbose_name(model, heading, case_insensitive=True)
            if attr is None:
                attribute_seq.append('')
            else:
                attribute_seq.append(attr.name)

        # load the data into objects
        objects = []
        errors = []
        transposed = model.Meta.tabular_orientation == TabularOrientation.column

        for row_num, obj_data in enumerate(data, start=2):
            obj = model()

            # save object location in file
            obj.set_source(reader.path, sheet_name, attribute_seq, row_num)

            obj_errors = []
            if ignore_extra_attributes:
                obj_data = list(compress(obj_data, good_columns))

            for attr, attr_value in zip(attributes, obj_data):
                try:
                    if not isinstance(attr, RelatedAttribute):
                        value, deserialize_error = attr.deserialize(attr_value)
                        validation_error = attr.validate(attr.__class__, value)
                        if deserialize_error or validation_error:
                            if deserialize_error:
                                deserialize_error.set_location_and_value(utils.source_report(obj, attr.name),
                                                                         attr_value)
                                obj_errors.append(deserialize_error)
                            if validation_error:
                                validation_error.set_location_and_value(utils.source_report(obj, attr.name),
                                                                        attr_value)
                                obj_errors.append(validation_error)
                        else:
                            setattr(obj, attr.name, value)

                except Exception as e:
                    error = InvalidAttribute(attr, ["{}".format(e)])
                    error.set_location_and_value(utils.source_report(obj, attr.name), attr_value)
                    obj_errors.append(error)

            if obj_errors:
                errors.append(InvalidObject(obj, obj_errors))

            objects.append(obj)

        model.get_manager().insert_all_new()
        return (attributes, data, errors, objects)

    def read_sheet(self, reader, sheet_name, num_row_heading_columns=0, num_column_heading_rows=0):
        """ Read file into a two-dimensional list

        Args:
            reader (:obj:`BaseReader`): reader
            sheet_name (:obj:`str`): worksheet name
            num_row_heading_columns (:obj:`int`, optional): number of columns of row headings
            num_column_heading_rows (:obj:`int`, optional): number of rows of column headings

        Returns:
            :obj:`tuple`:
                * `list` of `list`: two-dimensional list of table values
                * `list` of `list`: row headings
                * `list` of `list`: column_headings

        """
        data = reader.read_worksheet(sheet_name)

        # separate header rows
        column_headings = []
        for i_row in range(num_column_heading_rows):
            column_headings.append(data.pop(0))

        # separate header columns
        row_headings = []
        for i_col in range(num_row_heading_columns):
            row_heading = []
            row_headings.append(row_heading)
            for row in data:
                row_heading.append(row.pop(0))

            for column_heading in column_headings:
                column_heading.pop(0)

        return (data, row_headings, column_headings)

    def link_model(self, model, attributes, data, objects, objects_by_primary_attribute):
        """ Construct object graph

        Args:
            model (:obj:`Model`): an `obj_model.core.Model`
            attributes (:obj:`list` of `Attribute`): attribute order of `data`
            data (:obj:`list` of `list` of `object`): nested list of object data
            objects (:obj:`list`): list of model objects in order of `data`
            objects_by_primary_attribute (:obj:`dict`): dictionary of model objects grouped by model

        Returns:
            :obj:`list` of `str`: list of parsing errors
        """

        errors = []
        for obj_data, obj in zip(data, objects):
            for attr, attr_value in zip(attributes, obj_data):
                if isinstance(attr, RelatedAttribute):
                    value, error = attr.deserialize(attr_value, objects_by_primary_attribute)
                    if error:
                        error.set_location_and_value(utils.source_report(obj, attr.name), attr_value)
                        errors.append(error)
                    else:
                        setattr(obj, attr.name, value)

        return errors


def convert(source, destination, models=None):
    """ Convert among Excel (.xlsx), comma separated (.csv), and tab separated formats (.tsv)

    Args:
        source (:obj:`str`): path to source file
        destination (:obj:`str`): path to save converted file
        models (:obj:`list` of `class`, optional): list of models
    """
    models = models or []

    # get used sheet names
    _, ext = splitext(source)
    reader_cls = get_reader(ext)
    reader = reader_cls(source)
    reader.initialize_workbook()
    sheet_names = reader.get_sheet_names()
    del(reader)

    # determine order, style for sheets
    worksheet_order = []
    style = WorkbookStyle()
    for model in models:
        sheet_name = get_model_sheet_name(sheet_names, model)
        if sheet_name:
            worksheet_order.append(sheet_name)
            style[sheet_name] = Writer.create_worksheet_style(model)

    # convert
    base_convert(source, destination, worksheet_order=worksheet_order, style=style)


def create_template(path, models, title=None, description=None, keywords=None,
                    version=None, language=None, creator=None):
    """ Create a template for a model

    Args:
        path (:obj:`str`): path to write file(s)
        models (:obj:`list`): list of model, in the order that they should
            appear as worksheets; all models which are not in `models` will
            follow in alphabetical order
        title (:obj:`str`, optional): title
        description (:obj:`str`, optional): description
        keywords (:obj:`str`, optional): keywords
        version (:obj:`str`, optional): version
        language (:obj:`str`, optional): language
        creator (:obj:`str`, optional): creator
    """
    Writer().run(path, [], models,
                 title=title, description=description, keywords=keywords,
                 version=version, language=language, creator=creator)


def header_row_col_names(index, file_ext, tabular_orientation):
    """ Determine row and column names for header entries.

    Args:
        index (:obj:`int`): index in header sequence
        file_ext (:obj:`str`): extension for model file
        orientation (:obj:`TabularOrientation`): orientation of the stored table

    Returns:
        :obj:`tuple` of row, column, header_entries
    """
    if tabular_orientation == TabularOrientation.row:
        row, col, hdr_entries = (1, index, 'column')
    else:
        row, col, hdr_entries = (index, 1, 'row')
    if 'xlsx' in file_ext:
        col = excel_col_name(col)
    return (row, col, hdr_entries)


def get_model_sheet_name(sheet_names, model):
    """ Get the name of the worksheet/file which corresponds to a model

    Args:
        sheet_names (:obj:`list` of :obj:`str`): names of the sheets in the workbook/files
        model (:obj:`Model`): model

    Returns:
        :obj:`str`: name of sheet corresponding to the model or `None` if there is no sheet for the model

    Raises:
        :obj:`ValueError`: if the model matches more than one sheet
    """
    used_sheet_names = []
    possible_sheet_names = get_possible_model_sheet_names(model)
    for sheet_name in sheet_names:
        for possible_sheet_name in possible_sheet_names:
            if sheet_name.lower() == possible_sheet_name.lower():
                used_sheet_names.append(sheet_name)
                break

    used_sheet_names = list(set(used_sheet_names))
    if len(used_sheet_names) == 1:
        return used_sheet_names[0]
    if len(used_sheet_names) > 1:
        raise ValueError('Model {} matches multiple sheets'.format(model.__name__))
    return None


def get_possible_model_sheet_names(model):
    """ Return set of possible sheet names for a model

    Args:
        model (:obj:`Model`): Model

    Returns:
        :obj:`set`: set of possible sheet names for a model
    """
    return set([model.__name__, model.Meta.verbose_name, model.Meta.verbose_name_plural])


def get_ambiguous_sheet_names(sheet_names, models):
        """ Get names of sheets than cannot be unambiguously mapped to models (sheet names that map to multiple models).

        Args:
            sheet_names (:obj:`list` of :obj:`str`): names of the sheets in the workbook/files
            models (:obj:`list` of :obj:`Model`): list of models

        Returns:
            :obj:`dict` of :obj:`str`, :obj:`list` of :obj:`Model`: dictionary of ambiguous sheet names and their matching models
        """
        sheets_to_models = {}
        for sheet_name in sheet_names:
            sheets_to_models[sheet_name] = []
            for model in models:
                for possible_sheet_name in get_possible_model_sheet_names(model):
                    if sheet_name == possible_sheet_name:
                        sheets_to_models[sheet_name].append(model)

            if len(sheets_to_models[sheet_name]) <= 1:
                sheets_to_models.pop(sheet_name)

        return sheets_to_models


class IoWarning(ObjModelWarning):
    """ IO warning """
    pass