""" Unit attribute

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-01-20
:Copyright: 2019, Karr Lab
:License: MIT
"""

from . import core
import pint


class UnitAttribute(core.LiteralAttribute):
    """ Unit attribute

    Attributes:
        registry (:obj:`pint.UnitRegistry`): unit registry
        choices (:obj:`tuple` of :obj:registry.Unit): allowed values
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
    """

    def __init__(self, registry, choices=None, none=True, default=None, default_cleaned_value=None,
                 verbose_name='', help='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            registry (:obj:`pint.UnitRegistry`): unit registry
            choices (:obj:`tuple` of :obj:registry.Unit, optional): allowed units
            _choices (:obj:`tuple` of :obj:registry.Unit, optional): base of allowed units
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`str`, optional): default value
            default_cleaned_value (:obj:`str`, optional): value to replace :obj:`None` values with during cleaning
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
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

        if choices is None:
            _choices = None
        else:
            _choices = []
            for choice in choices:
                if not isinstance(choice, registry.Unit):
                    raise ValueError('choices must be instances of `registry.Unit`')
                _choices.append(registry.parse_expression(str(choice)).to_base_units().units)
            _choices = tuple(_choices)

        super(UnitAttribute, self).__init__(default=default,
                                            default_cleaned_value=default_cleaned_value,
                                            verbose_name=verbose_name, help=help,
                                            primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        self.registry = registry
        self.choices = choices
        self._choices = _choices
        self.none = none

    def get_default(self):
        """ Get default value for attribute

        Returns:
            :obj:registry.Unit: initial value
        """
        return self.default

    def get_default_cleaned_value(self):
        """ Get value to replace :obj:`None` values with during cleaning

        Returns:
            :obj:registry.Unit: initial value
        """
        return self.default_cleaned_value

    def value_equal(self, val1, val2):
        """ Determine if attribute values are equal

        Args:
            val1 (:obj:registry.Unit): first value
            val2 (:obj:registry.Unit): second value

        Returns:
            :obj:`bool`: True if attribute values are equal
        """
        if val1 is None:
            if val2 is None:
                return True
            return False
        else:
            if val2 is None:
                return False
            else:
                return (isinstance(val1, self.registry.Unit) and isinstance(val2, self.registry.Unit) and val1 == val2) or \
                    self.registry.parse_expression(str(val1)).to_base_units().units == \
                    self.registry.parse_expression(str(val2)).to_base_units().units

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
            except pint.UndefinedUnitError:
                error = 'Invalid unit {}'.format(value)
        else:
            error = 'Invalid unit {}'.format(value)
        return (value, error)

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:registry.Unit): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:registry.Unit: copy of value
        """
        return value

    def validate(self, obj, value):
        """ Determine if `value` is a valid value for this UnitAttribute

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:registry.Unit): value of attribute to validate

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
            value = self.registry.parse_expression(str(value)).to_base_units().units
            if self.choices and value not in self._choices:
                error = 'Value must be in `choices`'

        if error:
            return core.InvalidAttribute(self, [error])
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:registry.Unit): Python representation

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
            value (:obj:registry.Unit): value of the attribute

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
            :obj:registry.Unit: decoded value of the attribute
        """
        if json:
            return self.registry.parse_units(json)
        else:
            return None
