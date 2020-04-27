""" Attributes for symbolic math

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from .. import core
import sympy

__all__ = [
    'SymbolicBasicAttribute',
    'SymbolicSymbolAttribute',
    'SymbolicExprAttribute',
]


class SymbolicBasicAttribute(core.LiteralAttribute):
    """ Base class for SymPy expression, symbol attributes

    Attributes:
        sympy_type (:obj:`sympy.core.assumptions.ManagedProperties`): attribute type (e.g. :obj:`sympy.Basic`,
                :obj:`sympy.Expr`, :obj:`sympy.Symbol`)
        default (:obj:`sympy.Basic`): default value
    """

    def __init__(self, sympy_type=sympy.Basic, default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            sympy_type (:obj:`sympy.core.assumptions.ManagedProperties`, optional): attribute type (e.g. :obj:`sympy.Basic`,
                :obj:`sympy.Expr`, :obj:`sympy.Symbol`)
            default (:obj:`sympy.Basic`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        if default is not None and not isinstance(default, sympy_type):
            raise ValueError('Default must be a `{}` or `None`'.format(str(sympy_type)[8:-2]))

        super(SymbolicBasicAttribute, self).__init__(default=default, none_value=none_value,
                                                     verbose_name=verbose_name, description=description,
                                                     primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        self.sympy_type = sympy_type
        if primary:
            self.type = sympy_type
        else:
            self.type = (sympy_type, None.__class__)

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): semantically equivalent representation

        Returns:
            :obj:`tuple` of `sympy.Basic`, `core.InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value:
            value = self.sympy_type(value)
        else:
            value = None
        return (value, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`sympy.Basic`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of errors
                as an instance of `core.InvalidAttribute`
        """
        errors = []

        if value and not isinstance(value, self.sympy_type):
            errors.append('Value must be an instance of `{}`'.format(str(self.sympy_type)[8:-2]))
        elif self.primary and not value:
            errors.append('{} value for primary attribute cannot be empty'.format(
                self.__class__.__name__))

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def validate_unique(self, objects, values):
        """ Determine if the attribute values are unique

        Args:
            objects (:obj:`list` of :obj:`Model`): list of `Model` objects
            values (:obj:`list` of :obj:`sympy.Basic`): list of values

        Returns:
           :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a list
            of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(SymbolicBasicAttribute, self).validate_unique(objects, str_values)

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

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`sympy.Basic`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        else:
            return str(value)[6:-1]

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`list`): simple Python representation of a value of the attribute

        Returns:
            :obj:`sympy.Basic`: decoded value of the attribute
        """
        if json is None:
            return None
        else:
            return self.sympy_type(json)


class SymbolicExprAttribute(SymbolicBasicAttribute):
    """ SymPy expression attribute

    Attributes:
        default (:obj:`sympy.Expr`): default value
    """

    def __init__(self, default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            default (:obj:`sympy.Expr`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        super(SymbolicExprAttribute, self).__init__(sympy_type=sympy.Expr, default=default, none_value=none_value,
                                                    verbose_name=verbose_name, description=description,
                                                    primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`sympy.Expr`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            return str(value)[5:-1]
        return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`sympy.Expr`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        else:
            return str(value)[5:-1]


class SymbolicSymbolAttribute(SymbolicBasicAttribute):
    """ SymPy symbol attribute

    Attributes:
        default (:obj:`sympy.Symbol`): default value
    """

    def __init__(self, default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            default (:obj:`sympy.Symbol`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        super(SymbolicSymbolAttribute, self).__init__(sympy_type=sympy.Symbol, default=default, none_value=none_value,
                                                      verbose_name=verbose_name, description=description,
                                                      primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`sympy.Symbol`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            return str(value)
        return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`sympy.Symbol`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        else:
            return str(value)
