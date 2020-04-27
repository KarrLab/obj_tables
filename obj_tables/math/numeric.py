""" Math attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from .. import core
import json
import numpy
import pandas

__all__ = [
    'ArrayAttribute',
    'TableAttribute',
]


class ArrayAttribute(core.LiteralAttribute):
    """ numpy.ndarray attribute

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
        if not isinstance(min_length, (int, float)) or min_length < 0:
            raise ValueError('`min_length` must be a non-negative integer')
        if not isinstance(max_length, (int, float)) or max_length < min_length:
            raise ValueError('`max_length` must be an integer greater than or equal to `min_length`')

        super(ArrayAttribute, self).__init__(default=default, none_value=none_value,
                                             verbose_name=verbose_name, description=description,
                                             primary=primary, unique=unique)

        if primary:
            self.type = numpy.ndarray
        else:
            self.type = (numpy.ndarray, None.__class__)
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
        elif isinstance(value, str) and value == '':
            value = None
            error = None
        elif isinstance(value, str):
            try:
                value = numpy.array(json.loads(value), dtype)
                error = None
            except Exception:
                value = None
                error = 'Unable to parse numpy array from string'
        elif isinstance(value, (list, tuple, numpy.ndarray)):
            value = numpy.array(value, dtype)
            error = None
        else:
            value = None
            error = core.InvalidAttribute(self, [
                ('ArrayAttribute must be None, an empty string, '
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
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return
                list of errors as an instance of `core.InvalidAttribute`
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
            :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a
                list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(ArrayAttribute, self).validate_unique(objects, str_values)

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


class TableAttribute(core.LiteralAttribute):
    """ pandas.DataFrame attribute

    Attributes:
        default (:obj:`pandas.DataFrame`): default value
    """

    def __init__(self, default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False):
        """
        Args:
            default (:obj:`pandas.DataFrame`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        if default is not None and not isinstance(default, pandas.DataFrame):
            raise ValueError('`default` must be a `pandas.DataFrame` or `None`')

        super(TableAttribute, self).__init__(default=default, none_value=none_value,
                                             verbose_name=verbose_name, description=description,
                                             primary=primary, unique=unique)
        if primary:
            self.type = pandas.DataFrame
        else:
            self.type = (pandas.DataFrame, None.__class__)

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): semantically equivalent representation

        Returns:
            :obj:`tuple` of `pandas.DataFrame`, `core.InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if self.default is not None:
            dtype = self.default.values.dtype.type
        else:
            dtype = None

        if value is None:
            value = None
            error = None
        elif isinstance(value, str) and value == '':
            value = None
            error = None
        elif isinstance(value, str):
            try:
                dict_value = json.loads(value)
                index = dict_value.pop('_index')
                value = pandas.DataFrame.from_dict(dict_value, dtype=dtype)
                value.index = pandas.Index(index)
                error = None
            except Exception:
                value = None
                error = 'Unable to parse pandas.DataFrame from string'
        elif isinstance(value, dict):
            try:
                index = value.pop('_index')
                value = pandas.DataFrame(value)
                value = value.astype(dtype)
                value.index = pandas.Index(index)
                error = None
            except Exception:
                value = None
                error = 'Unable to parse pandas.DataFrame from dict'
        elif isinstance(value, pandas.DataFrame):
            error = None
        else:
            value = None
            error = core.InvalidAttribute(self, [
                ('TableAttribute must be None, an empty string, '
                 'a JSON-formatted dict, a dict, '
                 'or a pandas.DataFrame')
            ])
        return (value, error)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`pandas.DataFrame`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of
                errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if value is not None:
            if not isinstance(value, pandas.DataFrame):
                errors.append('Value must be an instance of `pandas.DataFrame`')
            elif self.default is not None:
                for elem in numpy.nditer(value.values):
                    if not issubclass(elem.dtype.type, self.default.values.dtype.type):
                        errors.append('Array elements must be of type `{}`'.format(self.default.values.dtype.type.__name__))
                        break

        if self.primary and (value is None or value.values.size == 0):
            errors.append('{} value for primary attribute cannot be empty'.format(
                self.__class__.__name__))

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def validate_unique(self, objects, values):
        """ Determine if the attribute values are unique

        Args:
            objects (:obj:`list` of :obj:`Model`): list of `Model` objects
            values (:obj:`list` of :obj:`pandas.DataFrame`): list of values

        Returns:
            :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a
                list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(TableAttribute, self).validate_unique(objects, str_values)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`pandas.DataFrame`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is not None:
            dict_value = value.to_dict()
            dict_value['_index'] = value.index.values.tolist()
            return json.dumps(dict_value)
        return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`pandas.DataFrame`): value of the attribute

        Returns:
            :obj:`dict`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        else:
            dict_value = value.to_dict()
            dict_value['_index'] = value.index.values.tolist()
            return dict_value

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`dict`): simple Python representation of a value of the attribute

        Returns:
            :obj:`pandas.DataFrame`: decoded value of the attribute
        """
        if json is None:
            return None
        else:
            if self.default is not None:
                dtype = self.default.values.dtype.type
            else:
                dtype = None
            index = json.pop('_index')
            value = pandas.DataFrame.from_dict(json, dtype=dtype)
            value.index = pandas.Index(index)
            return value
