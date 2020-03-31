""" Unit attribute

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-01-20
:Copyright: 2019, Karr Lab
:License: MIT
"""

from .. import core
from wc_utils.util.list import det_dedupe
from wc_utils.util.units import are_units_equivalent
import itertools
import math
import pint
import wc_utils.workbook.io

__all__ = [
    'UnitAttribute',
    'QuantityAttribute',
]


class UnitAttribute(core.LiteralAttribute):
    """ Unit attribute

    Attributes:
        registry (:obj:`pint.UnitRegistry`): unit registry
        choices (:obj:`tuple` of :obj:`pint.unit._Unit`): allowed values
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
    """

    def __init__(self, registry, choices=None, none=True, default=None, default_cleaned_value=None,
                 none_value=None, verbose_name='', description="Units (e.g. 'second', 'meter', or 'gram')",
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            registry (:obj:`pint.UnitRegistry`): unit registry
            choices (:obj:`tuple` of :obj:`pint.unit._Unit`, optional): allowed units
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`registry.Unit`, optional): default value
            default_cleaned_value (:obj:`registry.Unit`, optional): value to replace :obj:`None` values with during cleaning
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness

        Raises:
            :obj:`ValueError`: if registry is not an instance of `pint.UnitRegistry`
            :obj:`ValueError`: if default is not an instance of `registry.Unit`
            :obj:`ValueError`: if default_cleaned_value is not an instance of `registry.Unit`
            :obj:`ValueError`: if a choice is not an instance of `registry.Unit`
        """
        if not isinstance(registry, pint.UnitRegistry):
            raise ValueError('`registry` must be an instance of `pint.UnitRegistry`')
        if default is not None and not isinstance(default, registry.Unit):
            raise ValueError('`default` must be an instance of `registry.Unit`')
        if default_cleaned_value is not None and not isinstance(default_cleaned_value, registry.Unit):
            raise ValueError('`default_cleaned_value` must be an instance of `registry.Unit`')

        if choices is not None:
            for choice in choices:
                if not isinstance(choice, registry.Unit):
                    raise ValueError('choices must be instances of `registry.Unit`')

        super(UnitAttribute, self).__init__(default=default,
                                            default_cleaned_value=default_cleaned_value, none_value=none_value,
                                            verbose_name=verbose_name, description=description,
                                            primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        if primary:
            self.type = registry.Unit
        else:
            self.type = (registry.Unit, None.__class__)
        self.registry = registry
        self.choices = choices
        self.none = none

    def get_default(self):
        """ Get default value for attribute

        Returns:
            :obj:`pint.unit._Unit`: initial value
        """
        return self.default

    def get_default_cleaned_value(self):
        """ Get value to replace :obj:`None` values with during cleaning

        Returns:
            :obj:`pint.unit._Unit`: initial value
        """
        return self.default_cleaned_value

    def value_equal(self, val1, val2, tol=0.):
        """ Determine if attribute values are equal

        Args:
            val1 (:obj:`pint.unit._Unit`): first value
            val2 (:obj:`pint.unit._Unit`): second value
            tol (:obj:`float`, optional): equality tolerance

        Returns:
            :obj:`bool`: True if attribute values are equal
        """
        return are_units_equivalent(val1, val2, check_same_magnitude=True)

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of :obj:`str`, :obj:`core.InvalidAttribute` or :obj:`None`: tuple of cleaned value and cleaning error
        """
        error = None
        if isinstance(value, self.registry.Unit):
            pass
        elif value is None or value == '':
            value = self.get_default_cleaned_value()
        elif isinstance(value, str):
            try:
                value = self.registry.parse_units(value)
            except (pint.UndefinedUnitError, TypeError):
                error = core.InvalidAttribute(self, ['Invalid unit {}'.format(value)])
        else:
            error = core.InvalidAttribute(self, ['Invalid unit {}'.format(value)])
        return (value, error)

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`pint.unit._Unit`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`pint.unit._Unit`: copy of value
        """
        return value

    def validate(self, obj, value):
        """ Determine if `value` is a valid value for this UnitAttribute

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`pint.unit._Unit`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of
                errors as an instance of :obj:`core.InvalidAttribute`
        """
        error = None

        if value is None:
            if not self.none:
                error = 'Value must be an instance of `registry.Unit`'

        elif not isinstance(value, self.registry.Unit):
            error = 'Value must be an instance of `registry.Unit`'

        else:
            value = self.registry.parse_expression(str(value))
            if self.choices:
                valid = False
                for choice in self.choices:
                    try:
                        value.to(choice)
                        valid = True
                        break
                    except pint.DimensionalityError:
                        pass
                if not valid:
                    error = f"Value must be in `choices`: {set([str(c) for c in self.choices])}"

        if error:
            return core.InvalidAttribute(self, [error])
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`pint.unit._Unit`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            return str(value)
        else:
            return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`pint.unit._Unit`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        if value:
            return str(value)
        else:
            return None

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`str`): simple Python representation of a value of the attribute

        Returns:
            :obj:`pint.unit._Unit`: decoded value of the attribute
        """
        if json:
            return self.registry.parse_units(json)
        else:
            return None

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(UnitAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                     doc_metadata_model=doc_metadata_model)

        if self.choices is not None:
            allowed_values = [str(choice) for choice in self.choices]
            if len(','.join(allowed_values)) <= 255:
                validation.type = wc_utils.workbook.io.FieldValidationType.list
                validation.allowed_list_values = allowed_values

            validation.ignore_blank = self.none
            if self.none:
                input_message = ['Select one unit of "{}" or blank.'.format('", "'.join(allowed_values))]
                error_message = ['Value must be one unit of "{}" or blank.'.format('", "'.join(allowed_values))]
            else:
                input_message = ['Select one unit of "{}".'.format('", "'.join(allowed_values))]
                error_message = ['Value must be one unit of "{}".'.format('", "'.join(allowed_values))]

        else:
            validation.ignore_blank = self.none
            if self.none:
                input_message = ['Enter a unit or blank.']
                error_message = ['Value must be a unit or blank.']
            else:
                input_message = ['Enter a unit.']
                error_message = ['Value must be a unit.']

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default:
            input_message.append('Default: "{}".'.format(str(default)))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += '\n\n'.join(error_message)

        return validation


class QuantityAttribute(core.LiteralAttribute):
    """ Quantity (magntitude and units) attribute

    Attributes:
        registry (:obj:`pint.UnitRegistry`): unit registry
        choices (:obj:`tuple` of :obj:`pint.unit._Unit`): allowed units
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
    """

    def __init__(self, registry, choices=None, none=True, default=None, default_cleaned_value=None,
                 none_value=None, verbose_name='', description="Units (e.g. 'second', 'meter', or 'gram')",
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            registry (:obj:`pint.UnitRegistry`): unit registry
            choices (:obj:`tuple` of :obj:`pint.unit._Unit`, optional): allowed units
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`pint.unit.unit`, optional): default value
            default_cleaned_value (:obj:`str`, optional): value to replace :obj:`None` values with during cleaning
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness

        Raises:
            :obj:`ValueError`: if registry is not an instance of `pint.UnitRegistry`
            :obj:`ValueError`: if default is not an instance of `registry.Unit`
            :obj:`ValueError`: if default_cleaned_value is not an instance of `registry.Unit`
            :obj:`ValueError`: if a choice is not an instance of `registry.Unit`
        """
        if not isinstance(registry, pint.UnitRegistry):
            raise ValueError('`registry` must be an instance of `pint.UnitRegistry`')
        if default is not None and not isinstance(default, registry.Quantity):
            raise ValueError('`default` must be an instance of `registry.Quantity`')
        if default_cleaned_value is not None and not isinstance(default_cleaned_value, registry.Quantity):
            raise ValueError('`default_cleaned_value` must be an instance of `registry.Quantity`')

        if choices is not None:
            for choice in choices:
                if not isinstance(choice, registry.Unit):
                    raise ValueError('choices must be instances of `registry.Unit`')

        super(QuantityAttribute, self).__init__(default=default,
                                                default_cleaned_value=default_cleaned_value, none_value=none_value,
                                                verbose_name=verbose_name, description=description,
                                                primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        if primary:
            self.type = registry.Quantity
        else:
            self.type = (registry.Quantity, None.__class__)
        self.registry = registry
        self.choices = choices
        self.none = none

    def get_default(self):
        """ Get default value for attribute

        Returns:
            :obj:`pint.quantity._Quantity`: initial value
        """
        return self.default

    def get_default_cleaned_value(self):
        """ Get value to replace :obj:`None` values with during cleaning

        Returns:
            :obj:`pint.quantity._Quantity`: initial value
        """
        return self.default_cleaned_value

    def value_equal(self, val1, val2, tol=1e-12):
        """ Determine if attribute values are equal

        Args:
            val1 (:obj:`pint.quantity._Quantity`): first value
            val2 (:obj:`pint.quantity._Quantity`): second value
            tol (:obj:`float`, optional): equality tolerance

        Returns:
            :obj:`bool`: True if attribute values are equal
        """
        if not isinstance(val1, pint.quantity._Quantity) or not isinstance(val2, pint.quantity._Quantity):
            return val1 == val2

        if not are_units_equivalent(val1.units, val2.units, check_same_magnitude=False):
            return False
        mag1 = val1.m
        mag2 = val2.to(val1.units).m
        return mag1 == mag2 or \
            (math.isnan(mag1) and math.isnan(mag2)) or \
            (mag1 == 0. and abs(mag2) < tol) or \
            (mag1 != 0. and abs((mag1 - mag2) / mag1) < tol)

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of :obj:`str`, :obj:`core.InvalidAttribute` or :obj:`None`: tuple of cleaned value and cleaning error
        """
        error = None
        if isinstance(value, self.registry.Quantity):
            pass
        elif value is None or value == '':
            value = self.get_default_cleaned_value()
        elif isinstance(value, str):
            try:
                value = self.registry.parse_expression(value)
            except (pint.UndefinedUnitError, TypeError):
                error = core.InvalidAttribute(self, ['Invalid quantity {}'.format(value)])
        else:
            error = core.InvalidAttribute(self, ['Invalid quantity {}'.format(value)])
        return (value, error)

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`pint.quantity._Quantity`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`pint.quantity._Quantity`: copy of value
        """
        return self.registry.Quantity(value.m, value.units)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value for this QuantityAttribute

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`pint.quantity._Quantity`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of
                errors as an instance of :obj:`core.InvalidAttribute`
        """
        error = None

        if value is None:
            if not self.none:
                error = 'Value must be an instance of `registry.Quantity`'

        elif not isinstance(value, self.registry.Quantity):
            error = 'Value must be an instance of `registry.Quantity`'

        else:
            value = self.registry.parse_expression(str(value))
            if self.choices:
                valid = False
                for choice in self.choices:
                    try:
                        value.to(choice)
                        valid = True
                        break
                    except pint.DimensionalityError:
                        pass
                if not valid:
                    error = f"Value must be compatible with `choices`: {set([str(c) for c in self.choices])}"

        if error:
            return core.InvalidAttribute(self, [error])
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`pint.quantity._Quantity`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            return str(value)
        else:
            return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`pint.quantity._Quantity`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        if value:
            return {
                'magnitude': value.m,
                'units': str(value.units),
            }
        else:
            return None

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`str`): simple Python representation of a value of the attribute

        Returns:
            :obj:`pint.quantity._Quantity`: decoded value of the attribute
        """
        if json:
            return self.registry.Quantity(json['magnitude'], self.registry.parse_units(json['units']))
        else:
            return None

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(QuantityAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                         doc_metadata_model=doc_metadata_model)

        validation.ignore_blank = self.none
        if self.none:
            input_message = ['Enter a quantity or blank.']
            error_message = ['Value must be a quantity or blank.']
        else:
            input_message = ['Enter a quantity.']
            error_message = ['Value must be a quantity.']

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default:
            input_message.append('Default: "{}".'.format(str(default)))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += '\n\n'.join(error_message)

        return validation


def get_obj_units(obj):
    """ Get units used in a model object and related objects

    Args:
        obj (:obj:`core.Model`): model object

    Returns:
        :obj:`list` of :obj:`pint.unit._Unit`: units used in model object
    """
    units = []
    for o in itertools.chain([obj], obj.get_related()):
        for attr in o.Meta.attributes.values():
            if isinstance(attr, (UnitAttribute, QuantityAttribute)):
                unit = getattr(o, attr.name)
                if unit:
                    units.append(unit)

    # return units
    return det_dedupe(units)
