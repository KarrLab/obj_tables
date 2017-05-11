""" Additional attribute types

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from . import core
import Bio
import Bio.Alphabet
import Bio.Seq
import json
import six
import sympy


class BioSeqAttribute(core.Attribute):
    """ Bio.Seq.Seq attribute 

    Attributes:
        alphabet (:obj:`Bio.Alphabet.Alphabet`): alphabet
        min_length (:obj:`int`): minimum length
        max_length (:obj:`int`): maximum length
    """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, verbose_name='', help='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        if default is not None and not isinstance(default, Bio.Seq.Seq):
            raise ValueError('`default` must be a `Bio.Seq.Seq` or `None`')
        if not isinstance(min_length, (six.integer_types, float)) or min_length < 0:
            raise ValueError('`min_length` must be a non-negative number')
        if not isinstance(max_length, (six.integer_types, float)) or max_length < 0:
            raise ValueError('`max_length` must be a non-negative number')

        super(BioSeqAttribute, self).__init__(default=default,
                                              verbose_name=verbose_name, help=help,
                                              primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        self.alphabet = None
        self.min_length = min_length
        self.max_length = max_length

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`str`): value of attribute to clean

        Returns:
            :obj:`tuple` of `Bio.Seq.Seq`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
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
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = super(BioSeqAttribute, self).validate(obj, value)
        if errors:
            errors = errors.messages
        else:
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
           :obj:`InvalidAttribute` or None: None if values are unique, otherwise return a list of errors as an instance of `InvalidAttribute`
        """
        str_values = []
        for v in values:
            if v:
                str_values.append(str(v))
            else:
                str_values.append('')
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
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        super(BioDnaSeqAttribute, self).__init__(min_length=min_length, max_length=max_length, default=default,
                                                 verbose_name=verbose_name, help=help,
                                                 primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)
        self.alphabet = Bio.Alphabet.DNAAlphabet()


class BioProteinSeqAttribute(BioSeqAttribute):
    """ Bio.Seq.Seq attribute with Bio.Alphabet.ProteinAlphabet """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, verbose_name='', help='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        super(BioProteinSeqAttribute, self).__init__(min_length=min_length, max_length=max_length, default=default,
                                                     verbose_name=verbose_name, help=help,
                                                     primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)
        self.alphabet = Bio.Alphabet.ProteinAlphabet()


class BioRnaSeqAttribute(BioSeqAttribute):
    """ Bio.Seq.Seq attribute with Bio.Alphabet.RNAAlphabet """

    def __init__(self, min_length=0, max_length=float('inf'), default=None, verbose_name='', help='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`Bio.Seq.Seq`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        super(BioProteinSeqAttribute, self).__init__(min_length=min_length, max_length=max_length, default=default,
                                                     verbose_name=verbose_name, help=help,
                                                     primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)
        self.alphabet = Bio.Alphabet.RNAAlphabet()


class SympyBasicAttribute(core.Attribute):
    """ Base class for SymPy expression, symbol attributes 

    Attributes:
        type (:obj:`sympy.core.assumptions.ManagedProperties`): attribute type (e.g. :obj:`sympy.Basic`, 
                :obj:`sympy.Expr`, :obj:`sympy.Symbol`)
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
            values (:obj:`list` of :obj:`sympy.Basic`): list of values

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
