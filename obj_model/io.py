""" Reading/writing schema objects to/from files

* Comma separated values (.csv)
* Excel (.xlsx)
* JavaScript Object Notation (.json)
* Tab separated values (.tsv)
* Yet Another Markup Language (.yaml, .yml)

:Author: Jonathan Karr <karr@mssm.edu>
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

import abc
import collections
import copy
import inspect
import json
import six
import wc_utils.workbook.io
import yaml
from itertools import chain, compress
from natsort import natsorted, ns
from os.path import basename, dirname, splitext
from warnings import warn
from obj_model import utils
from obj_model.core import (Model, Attribute, RelatedAttribute, Validator, TabularOrientation,
                            InvalidObject, excel_col_name,
                            InvalidAttribute, ObjModelWarning)
from wc_utils.util.list import transpose
from wc_utils.workbook.core import get_column_letter
from wc_utils.workbook.io import WorkbookStyle, WorksheetStyle
from wc_utils.util.list import det_dedupe, is_sorted
from wc_utils.util.misc import quote
from wc_utils.util.string import indent_forest


class WriterBase(six.with_metaclass(abc.ABCMeta, object)):
    """ Interface for classes which write model objects to file(s) 

    Attributes:
        MODELS (:obj:`tuple` of :obj:`type`): default types of models to export and the order in which 
            to export them
    """

    MODELS = ()

    @abc.abstractmethod
    def run(self, path, objects, models=None, get_related=True, include_all_attributes=True, validate=True,
            title=None, description=None, keywords=None, version=None, language=None, creator=None):
        """ Write a list of model classes to an Excel file, with one worksheet for each model, or to
            a set of .csv or .tsv files, with one file for each model.

        Args:
            path (:obj:`str`): path to write file(s)
            objects (:obj:`Model` or :obj:`list` of :obj:`Model`): object or list of objects
            models (:obj:`list` of :obj:`Model`, optional): models
            get_related (:obj:`bool`, optional): if :obj:`True`, write object and all related objects
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
                not explictly included in `Model.Meta.attribute_order`
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data
            title (:obj:`str`, optional): title
            description (:obj:`str`, optional): description
            keywords (:obj:`str`, optional): keywords
            version (:obj:`str`, optional): version
            language (:obj:`str`, optional): language
            creator (:obj:`str`, optional): creator
        """
        pass  # pragma: no cover


class JsonWriter(WriterBase):
    """ Write model objects to a JSON or YAML file """

    def run(self, path, objects, models=None, get_related=True, include_all_attributes=True, validate=True,
            title=None, description=None, keywords=None, version=None, language=None, creator=None):
        """ Write a list of model classes to a JSON or YAML file

        Args:
            path (:obj:`str`): path to write file(s)
            objects (:obj:`Model` or :obj:`list` of :obj:`Model`): object or list of objects
            models (:obj:`list` of :obj:`Model`, optional): models
            get_related (:obj:`bool`, optional): if :obj:`True`, write object and all related objects
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
                not explictly included in `Model.Meta.attribute_order`
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data
            title (:obj:`str`, optional): title
            description (:obj:`str`, optional): description
            keywords (:obj:`str`, optional): keywords
            version (:obj:`str`, optional): version
            language (:obj:`str`, optional): language
            creator (:obj:`str`, optional): creator

        Raises:
            :obj:`ValueError`: if model names are not unique or output format is not supported
        """
        if models is None:
            models = self.MODELS
        if isinstance(models, (list, tuple)):
            models = list(models)
        else:
            models = [models]

        if not include_all_attributes:
            warn('`include_all_attributes=False` has no effect', IoWarning)

        # validate
        if objects and validate:
            error = Validator().run(objects, get_related=get_related)
            if error:
                warn('Some data will not be written because objects are not valid:\n  {}'.format(
                    str(error).replace('\n', '\n  ').rstrip()), IoWarning)

        # convert object(s) (and their relatives) to Python dicts and lists
        if objects is None:
            json_objects = None
        elif isinstance(objects, (list, tuple)):
            json_objects = []
            encoded = {}
            for obj in objects:
                json_objects.append(obj.to_dict(encoded=encoded))
                models.append(obj.__class__)
        else:
            json_objects = objects.to_dict()
            models.append(objects.__class__)

        # check that model names are unique so that objects will be decodable
        models = set(models)
        models_by_name = {model.__name__: model for model in models}
        if len(list(models_by_name.keys())) < len(models):
            raise ValueError('Model names must be unique to decode objects')

        # save plain Python object to JSON or YAML
        _, ext = splitext(path)
        ext = ext.lower()
        with open(path, 'w') as file:
            if ext == '.json':
                json.dump(json_objects, file)
            elif ext in ['.yaml', '.yml']:
                yaml.dump(json_objects, file, default_flow_style=False)
            else:
                raise ValueError('Unsupported format {}'.format(ext))


class WorkbookWriter(WriterBase):
    """ Write model objects to an Excel file or CSV or TSV file(s) """

    def run(self, path, objects, models=None, get_related=True, include_all_attributes=True, validate=True,
            title=None, description=None, keywords=None, version=None, language=None, creator=None):
        """ Write a list of model classes to an Excel file, with one worksheet for each model, or to
            a set of .csv or .tsv files, with one file for each model.

        Args:
            path (:obj:`str`): path to write file(s)
            objects (:obj:`Model` or :obj:`list` of :obj:`Model`): object or list of objects
            models (:obj:`list` of :obj:`Model`, optional): models in the order that they should
                appear as worksheets; all models which are not in `models` will
                follow in alphabetical order
            get_related (:obj:`bool`, optional): if :obj:`True`, write `objects` and all their related objects
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
                not explictly included in `Model.Meta.attribute_order`
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data
            title (:obj:`str`, optional): title
            description (:obj:`str`, optional): description
            keywords (:obj:`str`, optional): keywords
            version (:obj:`str`, optional): version
            language (:obj:`str`, optional): language
            creator (:obj:`str`, optional): creator            

        Raises:
            :obj:`ValueError`: if no model is provided or a class cannot be serialized
        """
        if objects is None:
            objects = []
        elif not isinstance(objects, (list, tuple)):
            objects = [objects]

        # get related objects
        all_objects = objects
        if get_related:
            all_objects = Model.get_all_related(objects)

        if validate:
            error = Validator().run(all_objects)
            if error:
                warn('Some data will not be written because objects are not valid:\n  {}'.format(
                    str(error).replace('\n', '\n  ').rstrip()), IoWarning)

        # group objects by class
        # todo: use dict_by_class
        grouped_objects = {}
        for obj in all_objects:
            if obj.__class__ not in grouped_objects:
                grouped_objects[obj.__class__] = []
            if obj not in grouped_objects[obj.__class__]:
                grouped_objects[obj.__class__].append(obj)

        # check that at least one model was provided
        if models is None:
            models = self.MODELS
        if isinstance(models, (list, tuple)):
            models = list(models)
        else:
            models = [models]
        for model in grouped_objects.keys():
            if model not in models:
                models.append(model)

        models = list(filter(lambda model: model.Meta.tabular_orientation != TabularOrientation.inline, models))

        if not models:
            raise ValueError('At least one `Model` must be provided')

        # check that models can be unambiguously mapped to worksheets
        sheet_names = []
        for model in models:
            if model.Meta.tabular_orientation == TabularOrientation.row:
                sheet_names.append(model.Meta.verbose_name_plural)
            else:
                sheet_names.append(model.Meta.verbose_name)
        ambiguous_sheet_names = WorkbookReader.get_ambiguous_sheet_names(sheet_names, models)
        if ambiguous_sheet_names:
            msg = 'The following sheets cannot be unambiguously mapped to models:'
            for sheet_name, models in ambiguous_sheet_names.items():
                msg += '\n  {}: {}'.format(sheet_name, ', '.join(model.__name__ for model in models))
            warn(msg, IoWarning)

        # check that models are serializble
        for cls in grouped_objects.keys():
            if not cls.is_serializable():
                raise ValueError('Class {}.{} cannot be serialized'.format(cls.__module__, cls.__name__))

        # get neglected models
        unordered_models = natsorted(set(grouped_objects.keys()).difference(set(models)),
                                     lambda model: model.Meta.verbose_name, alg=ns.IGNORECASE)

        # add sheets
        _, ext = splitext(path)
        writer_cls = wc_utils.workbook.io.get_writer(ext)
        writer = writer_cls(path,
                            title=title, description=description, keywords=keywords,
                            version=version, language=language, creator=creator)
        writer.initialize_workbook()

        encoded = {}
        for model in chain(models, unordered_models):
            if model.Meta.tabular_orientation == TabularOrientation.inline:
                continue

            if model in grouped_objects:
                objects = grouped_objects[model]
            else:
                objects = []

            self.write_model(writer, model, objects, include_all_attributes=include_all_attributes, encoded=encoded)

        writer.finalize_workbook()

    def write_model(self, writer, model, objects, include_all_attributes=True, encoded=None):
        """ Write a list of model objects to a file

        Args:
            writer (:obj:`wc_utils.workbook.io.Writer`): io writer
            model (:obj:`type`): model
            objects (:obj:`list` of :obj:`Model`): list of instances of `model`
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes
                including those not explictly included in `Model.Meta.attribute_order`
            encoded (:obj:`dict`, optional): objects that have already been encoded and their assigned JSON identifiers
        """

        # attribute order
        attributes = get_ordered_attributes(model, include_all_attributes=include_all_attributes)

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
                if isinstance(attr, RelatedAttribute):
                    obj_data.append(attr.serialize(getattr(obj, attr.name), encoded=encoded))
                else:
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
            style.auto_filter = False
            self.write_sheet(writer,
                             sheet_name=model.Meta.verbose_name,
                             data=transpose(data),
                             row_headings=headings,
                             style=style,
                             )

    def write_sheet(self, writer, sheet_name, data, row_headings=None, column_headings=None, style=None):
        """ Write data to sheet

        Args:
            writer (:obj:`wc_utils.workbook.io.Writer`): io writer
            sheet_name (:obj:`str`): sheet name
            data (:obj:`list` of :obj:`list` of :obj:`object`): list of list of cell values
            row_headings (:obj:`list` of :obj:`list` of :obj:`str`, optional): list of list of row headings
            column_headings (:obj:`list` of :obj:`list` of :obj:`str`, optional): list of list of column headings
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
            model (:obj:`type`): model class

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


class Writer(WriterBase):
    """ Write a list of model objects to file(s) """

    @staticmethod
    def get_writer(path):
        """ Get writer

        Args:
            path (:obj:`str`): path to write file(s)

        Returns:
            :obj:`type`: writer class

        Raises:
            :obj:`ValueError`: if extension is not supported
        """
        _, ext = splitext(path)
        ext = ext.lower()
        if ext in ['.csv', '.tsv', '.xlsx']:
            return WorkbookWriter
        elif ext in ['.json', '.yaml', '.yml']:
            return JsonWriter
        else:
            raise ValueError('Invalid export format: {}'.format(ext))

    def run(self, path, objects, models=None, get_related=True, include_all_attributes=True, validate=True,
            title=None, description=None, keywords=None, version=None, language=None, creator=None):
        """ Write a list of model classes to an Excel file, with one worksheet for each model, or to
            a set of .csv or .tsv files, with one file for each model.

        Args:
            path (:obj:`str`): path to write file(s)
            objects (:obj:`Model` or :obj:`list` of :obj:`Model`): object or list of objects
            models (:obj:`list` of :obj:`Model`, optional): models in the order that they should
                appear as worksheets; all models which are not in `models` will
                follow in alphabetical order
            get_related (:obj:`bool`, optional): if :obj:`True`, write object and all related objects
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
                not explictly included in `Model.Meta.attribute_order`
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data
            title (:obj:`str`, optional): title
            description (:obj:`str`, optional): description
            keywords (:obj:`str`, optional): keywords
            version (:obj:`str`, optional): version
            language (:obj:`str`, optional): language
            creator (:obj:`str`, optional): creator            
        """
        Writer = self.get_writer(path)
        Writer().run(path, objects, models=models, get_related=get_related,
                     include_all_attributes=include_all_attributes, validate=validate,
                     title=title, description=description, keywords=keywords,
                     language=language, creator=creator)


class ReaderBase(six.with_metaclass(abc.ABCMeta, object)):
    """ Interface for classes which write model objects to file(s)

    Attributes:
        MODELS (:obj:`tuple` of :obj:`type`): default types of models to export and the order in which 
            to export them
    """

    MODELS = ()

    @abc.abstractmethod
    def run(self, path, models=None,
            ignore_missing_sheets=False, ignore_extra_sheets=False, ignore_sheet_order=False,
            include_all_attributes=True, ignore_missing_attributes=False, ignore_extra_attributes=False, ignore_attribute_order=False,
            group_objects_by_model=False, validate=True):
        """ Read a list of model objects from file(s) and, optionally, validate them

        Args:
            path (:obj:`str`): path to file(s)
            models (:obj:`types.TypeType` or :obj:`list` of :obj:`types.TypeType`, optional): type
                of object to read or list of types of objects to read
            ignore_missing_sheets (:obj:`bool`, optional): if :obj:`False`, report an error if a worksheet/
                file is missing for one or more models
            ignore_extra_sheets (:obj:`bool`, optional): if :obj:`True` and all `models` are found, ignore
                other worksheets or files
            ignore_sheet_order (:obj:`bool`, optional): if :obj:`True`, do not require the sheets to be provided
                in the canonical order
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
                not explictly included in `Model.Meta.attribute_order`
            ignore_missing_attributes (:obj:`bool`, optional): if :obj:`False`, report an error if a
                worksheet/file doesn't contain all of attributes in a model in `models`
            ignore_extra_attributes (:obj:`bool`, optional): if :obj:`True`, do not report errors if
                attributes in the data are not in the model
            ignore_attribute_order (:obj:`bool`): if :obj:`True`, do not require the attributes to be provided
                in the canonical order
            group_objects_by_model (:obj:`bool`, optional): if :obj:`True`, group decoded objects by their
                types
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data

        Returns:
            :obj:`dict`: model objects grouped by `Model` class
        """
        pass  # pragma: no cover


class JsonReader(ReaderBase):
    """ Read model objects from a JSON or YAML file """

    def run(self, path, models=None,
            ignore_missing_sheets=False, ignore_extra_sheets=False, ignore_sheet_order=False,
            include_all_attributes=True, ignore_missing_attributes=False, ignore_extra_attributes=False, ignore_attribute_order=False,
            group_objects_by_model=False, validate=True):
        """ Read model objects from file(s) and, optionally, validate them

        Args:
            path (:obj:`str`): path to file(s)
            models (:obj:`types.TypeType` or :obj:`list` of :obj:`types.TypeType`, optional): type or list
                of type of objects to read
            ignore_missing_sheets (:obj:`bool`, optional): if :obj:`False`, report an error if a worksheet/
                file is missing for one or more models
            ignore_extra_sheets (:obj:`bool`, optional): if :obj:`True` and all `models` are found, ignore
                other worksheets or files
            ignore_sheet_order (:obj:`bool`, optional): if :obj:`True`, do not require the sheets to be provided
                in the canonical order
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
                not explictly included in `Model.Meta.attribute_order`
            ignore_missing_attributes (:obj:`bool`, optional): if :obj:`False`, report an error if a
                worksheet/file doesn't contain all of attributes in a model in `models`
            ignore_extra_attributes (:obj:`bool`, optional): if :obj:`True`, do not report errors if
                attributes in the data are not in the model
            ignore_attribute_order (:obj:`bool`): if :obj:`True`, do not require the attributes to be provided
                in the canonical order
            group_objects_by_model (:obj:`bool`, optional): if :obj:`True`, group decoded objects by their
                types
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data

        Returns:
            :obj:`dict`: model objects grouped by `Model` class

        Raises:
            :obj:`ValueError`: if the input format is not supported, model names are not unique, or the
                data is invalid
        """
        # cast models to list
        if models is None:
            models = self.MODELS
        if not isinstance(models, (list, tuple)):
            models = [models]

        # read the object into standard Python objects (lists, dicts)
        _, ext = splitext(path)
        ext = ext.lower()
        with open(path, 'r') as file:
            if ext == '.json':
                json_objs = json.load(file)
            elif ext in ['.yaml', '.yml']:
                json_objs = yaml.load(file)
            else:
                raise ValueError('Unsupported format {}'.format(ext))

        # check that model names are unique so that objects can be decoded
        models = set(models)
        models_by_name = {model.__name__: model for model in models}
        if len(list(models_by_name.keys())) < len(models):
            raise ValueError('Model names must be unique to decode objects')

        # cast the object(s) to their type
        if json_objs is None:
            objs = None

        elif isinstance(json_objs, list):
            objs = []
            decoded = {}
            for json_obj in json_objs:
                model = models_by_name[json_obj['__type']]
                objs.append(model.from_dict(json_obj, decoded=decoded))
            objs = det_dedupe(objs)

        else:
            model = models_by_name[json_objs['__type']]
            objs = model.from_dict(json_objs)

        # validate
        if objs and validate:
            if isinstance(objs, list):
                to_validate = objs
            else:
                to_validate = [objs]
            errors = Validator().validate(to_validate)
            if errors:
                raise ValueError(
                    indent_forest(['The model cannot be loaded because it fails to validate:', [errors]]))

        # group objects by model
        if group_objects_by_model:
            grouped_objs = {}
            if objs is None:
                objs = []
            elif not isinstance(objs, list):
                objs = [objs]
            for obj in objs:
                if obj.__class__ not in grouped_objs:
                    grouped_objs[obj.__class__] = []
                grouped_objs[obj.__class__].append(obj)
            return grouped_objs
        else:
            return objs


class WorkbookReader(ReaderBase):
    """ Read model objects from an Excel file or CSV and TSV files """

    def run(self, path, models=None,
            ignore_missing_sheets=False, ignore_extra_sheets=False, ignore_sheet_order=False,
            include_all_attributes=True, ignore_missing_attributes=False, ignore_extra_attributes=False, ignore_attribute_order=False,
            group_objects_by_model=True, validate=True):
        """ Read a list of model objects from file(s) and, optionally, validate them

        File(s) may be a single Excel workbook with multiple worksheets or a set of delimeter
        separated files encoded by a single path with a glob pattern.

        Args:
            path (:obj:`str`): path to file(s)
            models (:obj:`types.TypeType` or :obj:`list` of :obj:`types.TypeType`, optional): type or list
                of type of objects to read
            ignore_missing_sheets (:obj:`bool`, optional): if :obj:`False`, report an error if a worksheet/
                file is missing for one or more models
            ignore_extra_sheets (:obj:`bool`, optional): if :obj:`True` and all `models` are found, ignore
                other worksheets or files
            ignore_sheet_order (:obj:`bool`, optional): if :obj:`True`, do not require the sheets to be provided
                in the canonical order
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
                not explictly included in `Model.Meta.attribute_order`
            ignore_missing_attributes (:obj:`bool`, optional): if :obj:`False`, report an error if a
                worksheet/file doesn't contain all of attributes in a model in `models`
            ignore_extra_attributes (:obj:`bool`, optional): if :obj:`True`, do not report errors if
                attributes in the data are not in the model
            ignore_attribute_order (:obj:`bool`): if :obj:`True`, do not require the attributes to be provided
                in the canonical order
            group_objects_by_model (:obj:`bool`, optional): if :obj:`True`, group decoded objects by their
                types
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data

        Returns:
            :obj:`dict`: model objects grouped by `Model` class

        Raises:
            :obj:`ValueError`: if

                * Sheets cannot be unambiguously mapped to models
                * The file(s) indicated by :obj:`path` is missing a sheet for a model and
                  :obj:`ignore_missing_sheets` is :obj:`False`
                * The file(s) indicated by :obj:`path` contains extra sheets that don't correspond to one
                  of `models` and :obj:`ignore_extra_sheets` is :obj:`False`
                * The worksheets are file(s) indicated by :obj:`path` are not in the canonical order and
                  :obj:`ignore_sheet_order` is :obj:`False`
                * Some models are not serializable
                * The data contains parsing errors found by `read_model`
        """

        # initialize reader
        _, ext = splitext(path)
        ext = ext.lower()
        reader_cls = wc_utils.workbook.io.get_reader(ext)
        reader = reader_cls(path)

        # initialize reading
        reader.initialize_workbook()

        # check that at least one model is defined
        if models is None:
            models = self.MODELS
        if not isinstance(models, (list, tuple)):
            models = [models]

        # check that sheets can be unambiguously mapped to models
        sheet_names = reader.get_sheet_names()
        ambiguous_sheet_names = self.get_ambiguous_sheet_names(sheet_names, models)
        if ambiguous_sheet_names:
            msg = 'The following sheets cannot be unambiguously mapped to models:'
            for sheet_name, models in ambiguous_sheet_names.items():
                msg += '\n  {}: {}'.format(sheet_name, ', '.join(model.__name__ for model in models))
            raise ValueError(msg)

        # optionally,
        # * check every sheet is defined
        # * check no extra sheets are defined
        # * check the models are defined in the canonical order
        expected_sheet_names = []
        used_sheet_names = []
        sheet_order = []
        expected_sheet_order = []
        for model in models:
            model_sheet_name = self.get_model_sheet_name(sheet_names, model)
            if model_sheet_name:
                expected_sheet_names.append(model_sheet_name)
                used_sheet_names.append(model_sheet_name)
                sheet_order.append(sheet_names.index(model_sheet_name))
                expected_sheet_order.append(model_sheet_name)
            elif not inspect.isabstract(model):
                if model.Meta.tabular_orientation == TabularOrientation.row:
                    expected_sheet_names.append(model.Meta.verbose_name_plural)
                else:
                    expected_sheet_names.append(model.Meta.verbose_name)

        if not ignore_missing_sheets:
            missing_sheet_names = set(expected_sheet_names).difference(set(used_sheet_names))
            if missing_sheet_names:
                raise ValueError("Files/worksheets {} / '{}' must be defined".format(
                    basename(path), "', '".join(sorted(missing_sheet_names))))

        if not ignore_extra_sheets:
            extra_sheet_names = set(sheet_names).difference(set(used_sheet_names))
            if extra_sheet_names:
                raise ValueError("No matching models for worksheets/files {} / '{}'".format(
                    basename(path), "', '".join(sorted(extra_sheet_names))))

        if not ignore_sheet_order and ext == '.xlsx':
            if not is_sorted(sheet_order):
                raise ValueError('The sheets must be provided in this order:\n  {}'.format(
                    '\n  '.join(expected_sheet_order)))

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
            model_attributes, model_data, model_errors, model_objects = self.read_model(
                reader, model,
                include_all_attributes=include_all_attributes,
                ignore_missing_attributes=ignore_missing_attributes,
                ignore_extra_attributes=ignore_extra_attributes,
                ignore_attribute_order=ignore_attribute_order,
                validate=validate)
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
        decoded = {}
        for model, objects_model in objects.items():
            model_errors = self.link_model(model, attributes[model], data[model], objects_model,
                                           objects_by_primary_attribute, decoded=decoded)
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
            objects[model] = det_dedupe(objects[model] + list(model_objects.values()))

        # validate
        all_objects = []
        for model in models:
            all_objects.extend(objects[model])

        if validate:
            errors = Validator().validate(all_objects)
            if errors:
                raise ValueError(
                    indent_forest(['The model cannot be loaded because it fails to validate:', [errors]]))

        # return
        if group_objects_by_model:
            return objects
        else:
            if all_objects:
                return all_objects
            else:
                return None

    def read_model(self, reader, model, include_all_attributes=True,
                   ignore_missing_attributes=False, ignore_extra_attributes=False, ignore_attribute_order=False,
                   validate=True):
        """ Instantiate a list of objects from data in a table in a file

        Args:
            reader (:obj:`wc_utils.workbook.io.Reader`): reader
            model (:obj:`type`): the model describing the objects' schema
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
                not explictly included in `Model.Meta.attribute_order`
            ignore_missing_attributes (:obj:`bool`, optional): if :obj:`False`, report an error if the worksheet/files
                don't have all of attributes in the model
            ignore_extra_attributes (:obj:`bool`, optional): if :obj:`True`, do not report errors if attributes
                in the data are not in the model
            ignore_attribute_order (:obj:`bool`): if :obj:`True`, do not require the attributes to be provided in the
                canonical order
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data

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
        ext = ext.lower()
        sheet_name = self.get_model_sheet_name(reader.get_sheet_names(), model)
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
                row, col, hdr_entries = self.header_row_col_names(idx, ext, model.Meta.tabular_orientation)
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

        # optionally, check that all attributes have column headings
        if not ignore_missing_attributes:
            all_attributes = get_ordered_attributes(model, include_all_attributes=include_all_attributes)
            missing_attrs = set(all_attributes).difference(set(attributes))
            if missing_attrs:
                error = 'The following attributes must be defined:\n  {}'.format('\n  '.join(attr.name for attr in missing_attrs))
                return ([], [], [error], [])

        # optionally, check that the attributes are defined in the canonical order
        if not ignore_attribute_order:
            canonical_attr_order = get_ordered_attributes(model, include_all_attributes=include_all_attributes)
            canonical_attr_order = list(filter(lambda attr: attr in attributes, canonical_attr_order))
            if attributes != canonical_attr_order:
                column_headings = []
                for i_attr, attr in enumerate(canonical_attr_order):
                    column_headings.append('{}1: {}'.format(
                        get_column_letter(i_attr + 1),
                        attr.verbose_name))
                error = "The columns of worksheet '{}' must be defined in this order:\n  {}".format(
                    sheet_name, '\n  '.join(column_headings))
                return ([], [], [error], [])

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
        if not validate:
            errors = []
        return (attributes, data, errors, objects)

    def read_sheet(self, reader, sheet_name, num_row_heading_columns=0, num_column_heading_rows=0):
        """ Read file into a two-dimensional list

        Args:
            reader (:obj:`wc_utils.workbook.io.Reader`): reader
            sheet_name (:obj:`str`): worksheet name
            num_row_heading_columns (:obj:`int`, optional): number of columns of row headings
            num_column_heading_rows (:obj:`int`, optional): number of rows of column headings

        Returns:
            :obj:`tuple`:
                * `list` of `list`: two-dimensional list of table values
                * `list` of `list`: row headings
                * `list` of `list`: column_headings

        Raises:
            :obj:`ValueError`: if worksheet doesn't have header rows or columns
        """
        data = reader.read_worksheet(sheet_name)

        if len(data) < num_column_heading_rows:
            raise ValueError("Worksheet '{}' must have {} header row(s)".format(
                sheet_name, num_column_heading_rows))

        if (num_row_heading_columns > 0 and len(data) == 0) or len(data[0]) < num_row_heading_columns:
            raise ValueError("Worksheet '{}' must have {} header column(s)".format(
                sheet_name, num_row_heading_columns))

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

    def link_model(self, model, attributes, data, objects, objects_by_primary_attribute, decoded=None):
        """ Construct object graph

        Args:
            model (:obj:`Model`): an `obj_model.core.Model`
            attributes (:obj:`list` of :obj:`Attribute`): attribute order of `data`
            data (:obj:`list` of :obj:`list` of :obj:`object`): nested list of object data
            objects (:obj:`list`): list of model objects in order of `data`
            objects_by_primary_attribute (:obj:`dict`): dictionary of model objects grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`list` of :obj:`str`: list of parsing errors
        """

        errors = []
        for obj_data, obj in zip(data, objects):
            for attr, attr_value in zip(attributes, obj_data):
                if isinstance(attr, RelatedAttribute):
                    value, error = attr.deserialize(attr_value, objects_by_primary_attribute, decoded=decoded)
                    if error:
                        error.set_location_and_value(utils.source_report(obj, attr.name), attr_value)
                        errors.append(error)
                    else:
                        setattr(obj, attr.name, value)

        return errors

    @classmethod
    def header_row_col_names(cls, index, file_ext, tabular_orientation):
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

    @classmethod
    def get_model_sheet_name(cls, sheet_names, model):
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
        possible_sheet_names = cls.get_possible_model_sheet_names(model)
        for sheet_name in sheet_names:
            for possible_sheet_name in possible_sheet_names:
                if sheet_name.lower() == possible_sheet_name.lower():
                    used_sheet_names.append(sheet_name)
                    break

        used_sheet_names = det_dedupe(used_sheet_names)
        if len(used_sheet_names) == 1:
            return used_sheet_names[0]
        if len(used_sheet_names) > 1:
            raise ValueError('Model {} matches multiple sheets'.format(model.__name__))
        return None

    @classmethod
    def get_possible_model_sheet_names(cls, model):
        """ Return set of possible sheet names for a model

        Args:
            model (:obj:`Model`): Model

        Returns:
            :obj:`set`: set of possible sheet names for a model
        """
        return set([model.__name__, model.Meta.verbose_name, model.Meta.verbose_name_plural])

    @classmethod
    def get_ambiguous_sheet_names(cls, sheet_names, models):
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
                for possible_sheet_name in cls.get_possible_model_sheet_names(model):
                    if sheet_name == possible_sheet_name:
                        sheets_to_models[sheet_name].append(model)

            if len(sheets_to_models[sheet_name]) <= 1:
                sheets_to_models.pop(sheet_name)

        return sheets_to_models


class Reader(ReaderBase):
    @staticmethod
    def get_reader(path):
        """ Get reader

        Args:
            path (:obj:`str`): path to write file(s)

        Returns:
            :obj:`type`: reader class

        Raises:
            :obj:`ValueError`: if extension is not supported
        """
        _, ext = splitext(path)
        ext = ext.lower()
        if ext in ['.csv', '.tsv', '.xlsx']:
            return WorkbookReader
        elif ext in ['.json', '.yaml', '.yml']:
            return JsonReader
        else:
            raise ValueError('Invalid export format: {}'.format(ext))

    def run(self, path, models=None,
            ignore_missing_sheets=False, ignore_extra_sheets=False, ignore_sheet_order=False,
            include_all_attributes=True, ignore_missing_attributes=False, ignore_extra_attributes=False, ignore_attribute_order=False,
            group_objects_by_model=False, validate=True):
        """ Read a list of model objects from file(s) and, optionally, validate them

        Args:
            path (:obj:`str`): path to file(s)
            models (:obj:`types.TypeType` or :obj:`list` of :obj:`types.TypeType`, optional): type
                of object to read or list of types of objects to read
            ignore_missing_sheets (:obj:`bool`, optional): if :obj:`False`, report an error if a worksheet/
                file is missing for one or more models
            ignore_extra_sheets (:obj:`bool`, optional): if :obj:`True` and all `models` are found, ignore
                other worksheets or files
            ignore_sheet_order (:obj:`bool`, optional): if :obj:`True`, do not require the sheets to be provided
                in the canonical order
            include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
                not explictly included in `Model.Meta.attribute_order`
            ignore_missing_attributes (:obj:`bool`, optional): if :obj:`False`, report an error if a
                worksheet/file doesn't contain all of attributes in a model in `models`
            ignore_extra_attributes (:obj:`bool`, optional): if :obj:`True`, do not report errors if
                attributes in the data are not in the model
            ignore_attribute_order (:obj:`bool`): if :obj:`True`, do not require the attributes to be provided
                in the canonical order
            group_objects_by_model (:obj:`bool`, optional): if :obj:`True`, group decoded objects by their
                types
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data

        Returns:
            :obj:`dict`: model objects grouped by `Model` class
        """
        Reader = self.get_reader(path)
        return Reader().run(path, models=models,
                            ignore_missing_sheets=ignore_missing_sheets,
                            ignore_extra_sheets=ignore_extra_sheets,
                            ignore_sheet_order=ignore_sheet_order,
                            include_all_attributes=include_all_attributes,
                            ignore_missing_attributes=ignore_missing_attributes,
                            ignore_extra_attributes=ignore_extra_attributes,
                            ignore_attribute_order=ignore_attribute_order,
                            group_objects_by_model=group_objects_by_model,
                            validate=validate)


def convert(source, destination, models,
            ignore_missing_sheets=False, ignore_extra_sheets=False, ignore_sheet_order=False,
            include_all_attributes=True, ignore_missing_attributes=False, ignore_extra_attributes=False, ignore_attribute_order=False):
    """ Convert among comma-separated (.csv), Excel (.xlsx), JavaScript Object Notation (.json),
    tab-separated (.tsv), and Yet Another Markup Language (.yaml, .yml) formats

    Args:
        source (:obj:`str`): path to source file
        destination (:obj:`str`): path to save converted file
        models (:obj:`list` of :obj:`type`): list of models
        ignore_missing_sheets (:obj:`bool`, optional): if :obj:`False`, report an error if a worksheet/
            file is missing for one or more models
        ignore_extra_sheets (:obj:`bool`, optional): if :obj:`True` and all `models` are found, ignore
            other worksheets or files
        ignore_sheet_order (:obj:`bool`, optional): if :obj:`True`, do not require the sheets to be provided
            in the canonical order
        include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
            not explictly included in `Model.Meta.attribute_order`
        ignore_missing_attributes (:obj:`bool`, optional): if :obj:`False`, report an error if a
            worksheet/file doesn't contain all of attributes in a model in `models`
        ignore_extra_attributes (:obj:`bool`, optional): if :obj:`True`, do not report errors if
            attributes in the data are not in the model
        ignore_attribute_order (:obj:`bool`): if :obj:`True`, do not require the attributes to be provided
            in the canonical order
    """
    reader = Reader.get_reader(source)()
    writer = Writer.get_writer(destination)()

    kwargs = {}
    if isinstance(reader, WorkbookReader):
        kwargs['ignore_missing_sheets'] = ignore_missing_sheets
        kwargs['ignore_extra_sheets'] = ignore_extra_sheets
        kwargs['ignore_sheet_order'] = ignore_sheet_order
        kwargs['include_all_attributes'] = include_all_attributes
        kwargs['ignore_missing_attributes'] = ignore_missing_attributes
        kwargs['ignore_extra_attributes'] = ignore_extra_attributes
        kwargs['ignore_attribute_order'] = ignore_attribute_order
    objects = reader.run(source, models=models, group_objects_by_model=False, **kwargs)

    writer.run(destination, objects, models=models, get_related=False)


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
    Writer.get_writer(path)().run(path, [], models,
                                  title=title, description=description, keywords=keywords,
                                  version=version, language=language, creator=creator)


def get_ordered_attributes(cls, include_all_attributes=True):
    """ Get the attributes for a class in the order that they should be printed

    Args:
        include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
            not explictly included in `Model.Meta.attribute_order`

    Returns:
        :obj:`tuple` of :obj:`Attribute`: attributes in the order they should be printed
    """
    # get names of attributes in desired order
    if include_all_attributes:
        ordered_attr_names = list(cls.Meta.attribute_order)

        unordered_attr_names = set()
        for base in cls.Meta.inheritance:
            for attr_name in base.__dict__.keys():
                if isinstance(getattr(base, attr_name), Attribute) and attr_name not in ordered_attr_names:
                    unordered_attr_names.add(attr_name)

        unordered_attr_names = natsorted(unordered_attr_names, alg=ns.IGNORECASE)

        attr_names = tuple(ordered_attr_names + unordered_attr_names)
    else:
        attr_names = cls.Meta.attribute_order

    # get attributes in desired order
    return [cls.Meta.attributes[attr_name] for attr_name in attr_names]


class IoWarning(ObjModelWarning):
    """ IO warning """
    pass
