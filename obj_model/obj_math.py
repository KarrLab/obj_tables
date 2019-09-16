""" Math attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from . import core
import numpy
import sympy
import json
import six


class NumpyArrayAttribute(core.LiteralAttribute):
    """ numpy.array attribute

    Attributes:
        min_length (:obj:`int`): minimum length
        max_length (:obj:`int`): maximum length
        default (:obj:`numpy.ndarray`): default value
    """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`numpy.array`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        if default is not None and not isinstance(default, numpy.ndarray):
            raise ValueError('`default` must be a `numpy.array` or `None`')
        if not isinstance(min_length, (six.integer_types, float)) or min_length < 0:
            raise ValueError('`min_length` must be a non-negative integer')
        if not isinstance(max_length, (six.integer_types, float)) or max_length < min_length:
            raise ValueError('`max_length` must be an integer greater than or equal to `min_length`')

        super(NumpyArrayAttribute, self).__init__(default=default, none_value=none_value,
                                                  verbose_name=verbose_name, description=description,
                                                  primary=primary, unique=unique)

        self.min_length = min_length
        self.max_length = max_length

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): semantically equivalent representation

        Returns:
            :obj:`tuple` of `numpy.array`, `core.InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if self.default is not None:
            dtype = self.default.dtype.type
        else:
            dtype = None

        if value is None:
            value = None
            error = None
        elif isinstance(value, six.string_types) and value == '':
            value = None
            error = None
        elif isinstance(value, six.string_types):
            try:
                value = numpy.array(json.loads(value), dtype)
                error = None
            except:
                value = None
                error = 'Unable to parse numpy array from string'
        elif isinstance(value, (list, tuple, numpy.ndarray)):
            value = numpy.array(value, dtype)
            error = None
        else:
            value = None
            error = core.InvalidAttribute(self, [
                ('NumpyArrayAttribute must be None, an empty string, '
                 'a JSON-formatted array, a tuple, a list, '
                 'or a numpy array')
            ])
        return (value, error)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`numpy.array`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if value is not None:
            if not isinstance(value, numpy.ndarray):
                errors.append('Value must be an instance of `numpy.ndarray`')
            elif self.default is not None:
                for elem in numpy.nditer(value):
                    if not isinstance(elem, self.default.dtype.type):
                        errors.append('Array elements must be of type `{}`'.format(self.default.dtype.type.__name__))
                        break

        if self.min_length and (value is None or len(value) < self.min_length):
            errors.append('Value must be at least {:d} characters'.format(self.min_length))

        if self.max_length and value is not None and len(value) > self.max_length:
            errors.append('Value must be less than {:d} characters'.format(self.max_length))

        if self.primary and (value is None or len(value) == 0):
            errors.append('{} value for primary attribute cannot be empty'.format(
                self.__class__.__name__))

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def validate_unique(self, objects, values):
        """ Determine if the attribute values are unique

        Args:
            objects (:obj:`list` of :obj:`Model`): list of `Model` objects
            values (:obj:`list` of :obj:`numpy.array`): list of values

        Returns:
           :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(NumpyArrayAttribute, self).validate_unique(objects, str_values)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`numpy.array`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is not None:
            return json.dumps(value.tolist())
        return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`numpy.array`): value of the attribute

        Returns:
            :obj:`list`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        else:
            return value.tolist()

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`list`): simple Python representation of a value of the attribute

        Returns:
            :obj:`numpy.array`: decoded value of the attribute
        """
        if json is None:
            return None
        else:
            if self.default is not None:
                dtype = self.default.dtype.type
            else:
                dtype = None
            return numpy.array(json, dtype)


class SympyBasicAttribute(core.LiteralAttribute):
    """ Base class for SymPy expression, symbol attributes

    Attributes:
        type (:obj:`sympy.core.assumptions.ManagedProperties`): attribute type (e.g. :obj:`sympy.Basic`,
                :obj:`sympy.Expr`, :obj:`sympy.Symbol`)
        default (:obj:`sympy.Basic`): default value
    """

    def __init__(self, type=sympy.Basic, default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            type (:obj:`sympy.core.assumptions.ManagedProperties`, optional): attribute type (e.g. :obj:`sympy.Basic`,
                :obj:`sympy.Expr`, :obj:`sympy.Symbol`)
            default (:obj:`sympy.Basic`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        if default is not None and not isinstance(default, type):
            raise ValueError('Default must be a `{}` or `None`'.format(str(type)[8:-2]))

        super(SympyBasicAttribute, self).__init__(default=default, none_value=none_value,
                                                  verbose_name=verbose_name, description=description,
                                                  primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        self.type = type

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): semantically equivalent representation

        Returns:
            :obj:`tuple` of `sympy.Basic`, `core.InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
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
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `core.InvalidAttribute`
        """
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
            objects (:obj:`list` of :obj:`Model`): list of `Model` objects
            values (:obj:`list` of :obj:`sympy.Basic`): list of values

        Returns:
           :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
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
            return self.type(json)


class SympyExprAttribute(SympyBasicAttribute):
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
        super(SympyExprAttribute, self).__init__(type=sympy.Expr, default=default, none_value=none_value, verbose_name=verbose_name, description=description,
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


class SympySymbolAttribute(SympyBasicAttribute):
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
        super(SympySymbolAttribute, self).__init__(type=sympy.Symbol, default=default, none_value=none_value, verbose_name=verbose_name, description=description,
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
