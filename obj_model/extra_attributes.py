""" Additional attribute types

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from . import core
import Bio
import Bio.Alphabet
import Bio.motifs.matrix
import Bio.Seq
import Bio.SeqFeature
import json
import numpy
import six
import sympy


class FeatureLocationAttribute(core.Attribute):
    """ Bio.SeqFeature.FeatureLocation attribute

    Attributes:
        default (:obj:`Bio.SeqFeature.FeatureLocation`): defaultl value
    """

    def __init__(self, default=None, verbose_name='', help='',
                 primary=False, unique=False):
        """
        Args:
            default (:obj:`Bio.SeqFeature.FeatureLocation`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        if default is not None and not isinstance(default, Bio.SeqFeature.FeatureLocation):
            raise ValueError('`default` must be a `Bio.SeqFeature.FeatureLocation` or `None`')

        super(FeatureLocationAttribute, self).__init__(default=default,
                                                       verbose_name=verbose_name, help=help,
                                                       primary=primary, unique=unique)

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): semantically equivalent representation

        Returns:
            :obj:`tuple` of `numpy.array`, `core.InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value is None or value == '':
            value = None
            error = None
        elif isinstance(value, six.string_types):
            start, end, strand = map(int, value.split(','))
            value = Bio.SeqFeature.FeatureLocation(start, end, strand)
            error = None
        elif isinstance(value, (list, tuple)):
            stand, end, strand = value
            value = Bio.SeqFeature.FeatureLocation(stand, end, strand)
            error = None
        elif isinstance(value, Bio.SeqFeature.FeatureLocation):
            error = None
        else:
            value = None
            error = core.InvalidAttribute(self, [
                ('FeatureLocationAttribute must be None, an empty string, '
                 'a comma-separated string representation of a tuple, a tuple, a list, '
                 'or a Bio.SeqFeature.FeatureLocation')
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

        if value is not None and not isinstance(value, Bio.SeqFeature.FeatureLocation):
            errors.append('Value must be an instance of `Bio.SeqFeature.FeatureLocation`')

        if self.primary and value is None:
            errors.append('{} value for primary attribute cannot be empty'.format(
                self.__class__.__name__))

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def validate_unique(self, objects, values):
        """ Determine if the attribute values are unique

        Args:
            objects (:obj:`list` of `Model`): list of `Model` objects
            values (:obj:`list` of :obj:`Bio.SeqFeature.FeatureLocation`): list of values

        Returns:
           :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(FeatureLocationAttribute, self).validate_unique(objects, str_values)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`numpy.array`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is None:
            return ''
        else:
            return '{},{},{}'.format(value.start, value.end, value.strand)  # :todo: check if this is sufficient


class BioSeqAttribute(core.Attribute):
    """ Bio.Seq.Seq attribute 

    Attributes:
        _alphabet (:obj:`Bio.Alphabet.Alphabet`): alphabet
        min_length (:obj:`int`): minimum length
        max_length (:obj:`int`): maximum length
        default (:obj:`Bio.Seq.Seq`): default value
    """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, verbose_name='', help='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        if default is not None and not isinstance(default, Bio.Seq.Seq):
            raise ValueError('`default` must be a `Bio.Seq.Seq` or `None`')
        if not isinstance(min_length, (six.integer_types, float)) or min_length < 0:
            raise ValueError('`min_length` must be a non-negative integer')
        if not isinstance(max_length, (six.integer_types, float)) or max_length < min_length:
            raise ValueError('`max_length` must be an integer greater than or equal to `min_length`')

        super(BioSeqAttribute, self).__init__(default=default,
                                              verbose_name=verbose_name, help=help,
                                              primary=primary, unique=unique)

        self.alphabet = None
        self.min_length = min_length
        self.max_length = max_length

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): semantically equivalent representation

        Returns:
            :obj:`tuple` of `Bio.Seq.Seq`, `core.InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value:
            if self.alphabet:
                value = Bio.Seq.Seq(value, self.alphabet)
            else:
                tmp = json.loads(value)
                alphabet = getattr(Bio.Alphabet, tmp['alphabet']['type'])()
                alphabet.size = tmp['alphabet']['size']
                alphabet.letters = tmp['alphabet']['letters']
                value = Bio.Seq.Seq(tmp['seq'], alphabet)
        else:
            value = None
        return (value, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`Bio.Seq.Seq`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if value is not None:
            if not isinstance(value, Bio.Seq.Seq):
                errors.append('Value must be an instance of `Bio.Seq.`')
            elif self.alphabet and (
                    value.alphabet.__class__ != self.alphabet.__class__ or
                    value.alphabet.letters != self.alphabet.letters or
                    value.alphabet.size != self.alphabet.size):
                errors.append('The alphabet of value must be an instance of `{}`'.format(self.alphabet.__class__.__name__))

        if self.min_length and (not value or len(value) < self.min_length):
            errors.append('Value must be at least {:d} characters'.format(self.min_length))

        if self.max_length and value and len(value) > self.max_length:
            errors.append('Value must be less than {:d} characters'.format(self.max_length))

        if self.primary and (not value or len(value) == 0):
            errors.append('{} value for primary attribute cannot be empty'.format(
                self.__class__.__name__))

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def validate_unique(self, objects, values):
        """ Determine if the attribute values are unique

        Args:
            objects (:obj:`list` of `Model`): list of `Model` objects
            values (:obj:`list` of :obj:`Bio.Seq.Seq`): list of values

        Returns:
           :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(BioSeqAttribute, self).validate_unique(objects, str_values)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`Bio.Seq.Seq`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is not None:
            if self.alphabet:
                return str(value)
            else:
                return json.dumps({
                    'seq': str(value),
                    'alphabet': {
                        'type': value.alphabet.__class__.__name__,
                        'letters': value.alphabet.letters,
                        'size': value.alphabet.size,
                    },
                })
        return ''


class BioDnaSeqAttribute(BioSeqAttribute):
    """ Bio.Seq.Seq attribute with Bio.Alphabet.DNAAlphabet """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, verbose_name='', help='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(BioDnaSeqAttribute, self).__init__(min_length=min_length, max_length=max_length, default=default,
                                                 verbose_name=verbose_name, help=help,
                                                 primary=primary, unique=unique)
        self.alphabet = Bio.Alphabet.DNAAlphabet()


class BioProteinSeqAttribute(BioSeqAttribute):
    """ Bio.Seq.Seq attribute with Bio.Alphabet.ProteinAlphabet """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, verbose_name='', help='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(BioProteinSeqAttribute, self).__init__(min_length=min_length, max_length=max_length, default=default,
                                                     verbose_name=verbose_name, help=help,
                                                     primary=primary, unique=unique)
        self.alphabet = Bio.Alphabet.ProteinAlphabet()


class BioRnaSeqAttribute(BioSeqAttribute):
    """ Bio.Seq.Seq attribute with Bio.Alphabet.RNAAlphabet """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, verbose_name='', help='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(BioRnaSeqAttribute, self).__init__(min_length=min_length, max_length=max_length, default=default,
                                                 verbose_name=verbose_name, help=help,
                                                 primary=primary, unique=unique)
        self.alphabet = Bio.Alphabet.RNAAlphabet()


class FrequencyPositionMatrixAttribute(core.Attribute):
    """ Bio.motif.matrix.FrequencyPositionMatrix attribute """

    def __init__(self, verbose_name='', help=''):
        super(FrequencyPositionMatrixAttribute, self).__init__(
            default=None, verbose_name=verbose_name, help=help)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`Bio.motifs.matrix.FrequencyPositionMatrix`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `core.InvalidAttribute`
        """
        if value is not None and not isinstance(value, Bio.motifs.matrix.FrequencyPositionMatrix):
            return core.InvalidAttribute(self, ['Value must be an instance of `Bio.motifs.matrix.FrequencyPositionMatrix`'])
        return None

    def serialize(self, value):
        """ Serialize value to a string

        Args:
            value (:obj:`Bio.motifs.matrix.FrequencyPositionMatrix`): Python representation

        Returns:
            :obj:`str`: string representation
        """
        if not value:
            return ''

        dict_value = {
            '_alphabet': {
                'type': value.alphabet.__class__.__name__,
                'letters': value.alphabet.letters,
                'size': value.alphabet.size,
            },
        }
        for letter, counts in value.items():
            dict_value[letter] = counts

        return json.dumps(dict_value)

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): string representation

        Returns:
            :obj:`tuple` of `Bio.motifs.matrix.FrequencyPositionMatrix`, `core.InvalidAttribute` or `None`: 
                tuple of cleaned value and cleaning error
        """
        if value:
            try:
                dict_value = json.loads(value)

                alphabet = getattr(Bio.Alphabet, dict_value['_alphabet']['type'])()
                alphabet.size = dict_value['_alphabet']['size']
                alphabet.letters = dict_value['_alphabet']['letters']
                dict_value.pop('_alphabet')

                return (Bio.motifs.matrix.FrequencyPositionMatrix(alphabet, dict_value), None)
            except Exception as error:
                return (None, core.InvalidAttribute(self, [str(error)]))
        else:
            return (None, None)


class NumpyArrayAttribute(core.Attribute):
    """ numpy.array attribute

    Attributes:
        min_length (:obj:`int`): minimum length
        max_length (:obj:`int`): maximum length
        default (:obj:`numpy.ndarray`): default value
    """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, verbose_name='', help='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`numpy.array`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        if default is not None and not isinstance(default, numpy.ndarray):
            raise ValueError('`default` must be a `numpy.array` or `None`')
        if not isinstance(min_length, (six.integer_types, float)) or min_length < 0:
            raise ValueError('`min_length` must be a non-negative integer')
        if not isinstance(max_length, (six.integer_types, float)) or max_length < min_length:
            raise ValueError('`max_length` must be an integer greater than or equal to `min_length`')

        super(NumpyArrayAttribute, self).__init__(default=default,
                                                  verbose_name=verbose_name, help=help,
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
            objects (:obj:`list` of `Model`): list of `Model` objects
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


class SympyBasicAttribute(core.Attribute):
    """ Base class for SymPy expression, symbol attributes 

    Attributes:
        type (:obj:`sympy.core.assumptions.ManagedProperties`): attribute type (e.g. :obj:`sympy.Basic`, 
                :obj:`sympy.Expr`, :obj:`sympy.Symbol`)
        default (:obj:`sympy.Basic`): default value
    """

    def __init__(self, type=sympy.Basic, default=None, verbose_name='', help='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            type (:obj:`sympy.core.assumptions.ManagedProperties`, optional): attribute type (e.g. :obj:`sympy.Basic`, 
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
            objects (:obj:`list` of `Model`): list of `Model` objects
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


class SympyExprAttribute(SympyBasicAttribute):
    """ SymPy expression attribute 

    Attributes:
        default (:obj:`sympy.Expr`): default value
    """

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
    """ SymPy symbol attribute 

    Attributes:
        default (:obj:`sympy.Symbol`): default value
    """

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
