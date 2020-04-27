""" Uncertain value attribute

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2012-03-05
:Copyright: 2020, Karr Lab
:License: MIT
"""

from .. import core
import math
import uncertainties
import wc_utils.workbook.io  # noqa: F401

__all__ = [
    'UncertainFloatAttribute',
]


class UncertainFloatAttribute(core.LiteralAttribute):
    """ Attribute for a value and its uncertainty

    Attributes:
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
    """

    def __init__(self, none=True, default=None, default_cleaned_value=None,
                 none_value=None, verbose_name='', description="Measurement (e.g. 'x ± y')",
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`uncertainties.core.Variable`, optional): default value
            default_cleaned_value (:obj:`uncertainties.core.Variable`, optional): value to replace :obj:`None` values with during cleaning
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        if default is not None and not isinstance(default, uncertainties.core.Variable):
            raise ValueError('`default` must be an instance of `uncertainties.core.Variable`')
        if default_cleaned_value is not None and not isinstance(default_cleaned_value, uncertainties.core.Variable):
            raise ValueError('`default_cleaned_value` must be an instance of `uncertainties.core.Variable`')

        super(UncertainFloatAttribute, self).__init__(default=default,
                                                      default_cleaned_value=default_cleaned_value, none_value=none_value,
                                                      verbose_name=verbose_name, description=description,
                                                      primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)
        if none and not primary:
            self.type = (uncertainties.core.Variable, None.__class__)
        else:
            self.type = uncertainties.core.Variable
        self.none = none

    def get_default(self):
        """ Get default value for attribute

        Returns:
            :obj:`uncertainties.core.Variable`: initial value
        """
        return self.default

    def get_default_cleaned_value(self):
        """ Get value to replace :obj:`None` values with during cleaning

        Returns:
            :obj:`uncertainties.core.Variable`: initial value
        """
        return self.default_cleaned_value

    def value_equal(self, val1, val2, tol=0.):
        """ Determine if attribute values are equal

        Args:
            val1 (:obj:`uncertainties.core.Variable`): first value
            val2 (:obj:`uncertainties.core.Variable`): second value
            tol (:obj:`float`, optional): equality tolerance

        Returns:
            :obj:`bool`: True if attribute values are equal
        """
        def val_eq(val1, val2, tol):
            return val1 == val2 or \
                (math.isnan(val1) and math.isnan(val2)) or \
                (val1 == 0. and abs(val2) < tol) or \
                (val1 != 0. and abs((val1 - val2) / val1) < tol)
        return val1 == val2 or (isinstance(val1, uncertainties.core.Variable)
                                and isinstance(val2, uncertainties.core.Variable)
                                and val_eq(val1.n, val2.n, tol)
                                and val_eq(val1.s, val2.s, tol))

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of :obj:`str`, :obj:`core.InvalidAttribute` or :obj:`None`:
                tuple of cleaned value and cleaning error
        """
        error = None
        if isinstance(value, uncertainties.core.Variable):
            pass
        elif value is None or value == '':
            value = self.get_default_cleaned_value()
        elif isinstance(value, str):
            try:
                value = uncertainties.ufloat_fromstr(value)
            except ValueError:
                error = core.InvalidAttribute(self, ['Invalid uncertain float {}'.format(value)])
        else:
            error = core.InvalidAttribute(self, ['Invalid uncertain float {}'.format(value)])
        return (value, error)

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`uncertainties.core.Variable`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`uncertainties.core.Variable`: copy of value
        """
        if value is None:
            return None
        return uncertainties.ufloat(value.n, value.s)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value for this UncertainFloatAttribute

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`uncertainties.core.Variable`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of
                errors as an instance of :obj:`core.InvalidAttribute`
        """
        error = None

        if value is None:
            if not self.none:
                error = 'Value must be an instance of `uncertainties.core.Variable`'

        elif not isinstance(value, uncertainties.core.Variable):
            error = 'Value must be an instance of `uncertainties.core.Variable`'

        if error:
            return core.InvalidAttribute(self, [error])
        return None

    def serialize(self, value):
        """ Serialize to a string

        Args:
            value (:obj:`uncertainties.core.Variable`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            return '{} ± {}'.format(value.n, value.s)
        else:
            return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`uncertainties.core.Variable`): value of the attribute

        Returns:
            :obj:`dict`: simple Python representation of a value of the attribute
        """
        if value:
            return {
                'nominal_value': value.n,
                'std_dev': value.s,
            }
        else:
            return None

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`dict`): simple Python representation of a value of the attribute

        Returns:
            :obj:`uncertainties.core.Variable`: decoded value of the attribute
        """
        if json:
            return uncertainties.ufloat(json['nominal_value'], json['std_dev'])
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
        validation = super(UncertainFloatAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                               doc_metadata_model=doc_metadata_model)

        validation.ignore_blank = self.none
        if self.none:
            input_message = ['Enter a value and uncertainty or blank.']
            error_message = ['Value must be a value and uncertainty or blank.']
        else:
            input_message = ['Enter a value and uncertainty.']
            error_message = ['Value must be a value and uncertainty.']

        if self.unique:
            input_message.append('Value and uncertainty must be unique.')
            error_message.append('Value and uncertainty must be unique.')

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
