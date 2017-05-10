""" Additional attribute types

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from . import core
import sympy


class SympyBasicAttribute(core.Attribute):
    """ Base class for SymPy expression, symbol attributes """

    def __init__(self, type=sympy.Basic, default=None, verbose_name='', help='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            type (:obj:`sympy.core.assumptions.ManagedProperties`): attribute type (e.g. :obj:`sympy.Basic`, 
                :obj:`sympy.Expr`, :obj:`sympy.Symbol`)
            default (:obj:`sympy.Basic`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        if default is not None and not isinstance(default, type):
            raise ValueError('Default must be a `{}` or `None`'.format(str(type)[8:-2]))

        super(SympyBasicAttribute, self).__init__(default=default,
                                                  verbose_name=verbose_name, help=help,
                                                  primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        self.type = type

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`str`): value of attribute to clean

        Returns:
            :obj:`tuple` of `sympy.Basic`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value:
            value = self.type(value)
        else:
            value = None
        return (value, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`sympy.Basic`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = super(SympyBasicAttribute, self).validate(obj, value)
        if errors:
            errors = errors.messages
        else:
            errors = []

        if value and not isinstance(value, self.type):
            errors.append('Value must be an instance of `{}`'.format(str(self.type)[8:-2]))
        elif self.primary and not value:
            errors.append('{} value for primary attribute cannot be empty'.format(
                self.__class__.__name__))

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def validate_unique(self, objects, values):
        """ Determine if the attribute values are unique

        Args:
            objects (:obj:`list` of `Model`): list of `Model` objects
            values (:obj:`list`): list of values

        Returns:
           :obj:`InvalidAttribute` or None: None if values are unique, otherwise return a list of errors as an instance of `InvalidAttribute`
        """
        str_values = []
        for v in values:
            if v:
                str_values.append(str(v))
            else:
                str_values.append('')
        return super(SympyBasicAttribute, self).validate_unique(objects, str_values)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`sympy.Basic`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            return str(value)[6:-1]
        return ''


class SympyExprAttribute(SympyBasicAttribute):
    """ SymPy expression attribute """

    def __init__(self, default=None, verbose_name='', help='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            default (:obj:`sympy.Expr`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        super(SympyExprAttribute, self).__init__(type=sympy.Expr, default=default, verbose_name=verbose_name, help=help,
                                                 primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`sympy.Basic`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            return str(value)[5:-1]
        return ''


class SympySymbolAttribute(SympyBasicAttribute):
    """ SymPy symbol attribute """

    def __init__(self, default=None, verbose_name='', help='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            default (:obj:`sympy.Symbol`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        super(SympySymbolAttribute, self).__init__(type=sympy.Symbol, default=default, verbose_name=verbose_name, help=help,
                                                   primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`sympy.Basic`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            return str(value)
        return ''
