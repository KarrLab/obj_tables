""" Biological attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from obj_tables import core
import Bio
import Bio.Alphabet
import Bio.motifs.matrix
import Bio.Seq
import Bio.SeqFeature
import copy
import json

__all__ = [
    'FeatureLocAttribute',
    'SeqAttribute',
    'DnaSeqAttribute',
    'RnaSeqAttribute',
    'ProteinSeqAttribute',
    'FreqPosMatrixAttribute'
]


class FeatureLocAttribute(core.LiteralAttribute):
    """ Bio.SeqFeature.FeatureLocation attribute

    Attributes:
        default (:obj:`Bio.SeqFeature.FeatureLocation`): default value
    """

    def __init__(self, default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False):
        """
        Args:
            default (:obj:`Bio.SeqFeature.FeatureLocation`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        if default is not None and not isinstance(default, Bio.SeqFeature.FeatureLocation):
            raise ValueError('`default` must be a `Bio.SeqFeature.FeatureLocation` or `None`')

        super(FeatureLocAttribute, self).__init__(default=default, none_value=none_value,
                                                  verbose_name=verbose_name,
                                                  description=description,
                                                  primary=primary, unique=unique)
        if primary:
            self.type = Bio.SeqFeature.FeatureLocation
        else:
            self.type = (Bio.SeqFeature.FeatureLocation, None.__class__)

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
        elif isinstance(value, str):
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
                ('FeatureLocAttribute must be None, an empty string, '
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
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return
                list of errors as an instance of `core.InvalidAttribute`
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
            objects (:obj:`list` of :obj:`Model`): list of `Model` objects
            values (:obj:`list` of :obj:`Bio.SeqFeature.FeatureLocation`): list of values

        Returns:
            :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return
                a list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(FeatureLocAttribute, self).validate_unique(objects, str_values)

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

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`Bio.SeqFeature.FeatureLocation`): value of the attribute

        Returns:
            :obj:`dict`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        else:
            return {'start': value.start, 'end': value.end, 'strand': value.strand}

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`dict`): simple Python representation of a value of the attribute

        Returns:
            :obj:`Bio.SeqFeature.FeatureLocation`: decoded value of the attribute
        """
        if json is None:
            return None
        else:
            return Bio.SeqFeature.FeatureLocation(json['start'], json['end'], json['strand'])


class SeqAttribute(core.LiteralAttribute):
    """ Bio.Seq.Seq attribute

    Attributes:
        _alphabet (:obj:`Bio.Alphabet.Alphabet`): alphabet
        min_length (:obj:`int`): minimum length
        max_length (:obj:`int`): maximum length
        default (:obj:`Bio.Seq.Seq`): default value
    """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        if default is not None and not isinstance(default, Bio.Seq.Seq):
            raise ValueError('`default` must be a `Bio.Seq.Seq` or `None`')
        if not isinstance(min_length, (int, float)) or min_length < 0:
            raise ValueError('`min_length` must be a non-negative integer')
        if not isinstance(max_length, (int, float)) or max_length < min_length:
            raise ValueError('`max_length` must be an integer greater than or equal to `min_length`')

        super(SeqAttribute, self).__init__(default=default, none_value=none_value,
                                           verbose_name=verbose_name,
                                           description=description,
                                           primary=primary, unique=unique)

        if primary or min_length:
            self.type = Bio.Seq.Seq
        else:
            self.type = (Bio.Seq.Seq, None.__class__)
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
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return
                list of errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if value is not None:
            if not isinstance(value, Bio.Seq.Seq):
                errors.append('Value must be an instance of `Bio.Seq.Seq`')
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
            objects (:obj:`list` of :obj:`Model`): list of `Model` objects
            values (:obj:`list` of :obj:`Bio.Seq.Seq`): list of values

        Returns:
            :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return
                a list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(SeqAttribute, self).validate_unique(objects, str_values)

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

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`Bio.Seq.Seq`): value of the attribute

        Returns:
            :obj:`dict`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        else:
            return {
                'seq': str(value),
                'alphabet': {
                    'type': value.alphabet.__class__.__name__,
                    'letters': value.alphabet.letters,
                    'size': value.alphabet.size,
                },
            }

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`dict`): simple Python representation of a value of the attribute

        Returns:
            :obj:`Bio.Seq.Seq`: decoded value of the attribute
        """
        if json is None:
            return None
        else:
            alphabet = getattr(Bio.Alphabet, json['alphabet']['type'])()
            alphabet.size = json['alphabet']['size']
            alphabet.letters = json['alphabet']['letters']
            return Bio.Seq.Seq(json['seq'], alphabet)


class DnaSeqAttribute(SeqAttribute):
    """ Bio.Seq.Seq attribute with Bio.Alphabet.DNAAlphabet """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(DnaSeqAttribute, self).__init__(min_length=min_length, max_length=max_length, default=default,
                                              none_value=none_value, verbose_name=verbose_name,
                                              description=description,
                                              primary=primary, unique=unique)
        self.alphabet = Bio.Alphabet.DNAAlphabet()


class ProteinSeqAttribute(SeqAttribute):
    """ Bio.Seq.Seq attribute with Bio.Alphabet.ProteinAlphabet """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(ProteinSeqAttribute, self).__init__(min_length=min_length, max_length=max_length, default=default,
                                                  none_value=none_value, verbose_name=verbose_name,
                                                  description=description,
                                                  primary=primary, unique=unique)
        self.alphabet = Bio.Alphabet.ProteinAlphabet()


class RnaSeqAttribute(SeqAttribute):
    """ Bio.Seq.Seq attribute with Bio.Alphabet.RNAAlphabet """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(RnaSeqAttribute, self).__init__(min_length=min_length, max_length=max_length, default=default,
                                              none_value=none_value, verbose_name=verbose_name,
                                              description=description,
                                              primary=primary, unique=unique)
        self.alphabet = Bio.Alphabet.RNAAlphabet()


class FreqPosMatrixAttribute(core.LiteralAttribute):
    """ Bio.motifs.matrix.FrequencyPositionMatrix attribute """

    def __init__(self, verbose_name='', description=''):
        super(FreqPosMatrixAttribute, self).__init__(
            default=None, verbose_name=verbose_name,
            description=description)
        self.type = (Bio.motifs.matrix.FrequencyPositionMatrix, None.__class__)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`Bio.motifs.matrix.FrequencyPositionMatrix`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list
                of errors as an instance of `core.InvalidAttribute`
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
            '_alphabet': value.alphabet,
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

                alphabet = dict_value['_alphabet']
                dict_value.pop('_alphabet')

                return (Bio.motifs.matrix.FrequencyPositionMatrix(alphabet, dict_value), None)
            except Exception as error:
                return (None, core.InvalidAttribute(self, [str(error)]))
        else:
            return (None, None)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`Bio.motifs.matrix.FrequencyPositionMatrix`): value of the attribute

        Returns:
            :obj:`dict`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        else:
            json = {
                '_alphabet': value.alphabet,
            }
            for letter, counts in value.items():
                json[letter] = counts
            return json

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`dict`): simple Python representation of a value of the attribute

        Returns:
            :obj:`Bio.motifs.matrix.FrequencyPositionMatrix`: decoded value of the attribute
        """
        if json is None:
            return None
        else:
            json = copy.copy(json)
            alphabet = json['_alphabet']
            json.pop('_alphabet')
            return Bio.motifs.matrix.FrequencyPositionMatrix(alphabet, json)
