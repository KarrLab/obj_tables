""" Ontology attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-01-14
:Copyright: 2019, Karr Lab
:License: MIT
"""

from . import core
import pronto


class OntologyAttribute(core.LiteralAttribute):
    """ Ontology attribute

    Attributes:
        ontology (obj:`pronto.Ontology`): ontology
        terms (:obj:`list` of :obj:`pronto.term.Term`): list of allowed terms. If :obj:`None`, all terms are allowed.
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
    """

    def __init__(self, ontology, terms=None, none=True, default=None, default_cleaned_value=None, verbose_name='', help='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            ontology (:obj:`pronto.Ontology`): ontology
            terms (:obj:`list` of :obj:`pronto.term.Term`, optional): list of allowed terms. If :obj:`None`, all terms are allowed.
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`pronto.term.Term`, optional): default value
            default_cleaned_value (:obj:`pronto.term.Term`, optional): value to replace
                :obj:`None` values with during cleaning
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness

        Raises:
            :obj:`ValueError`: if :obj:`ontology` is not an instance of :obj:`pronto.Ontology`,
            :obj:`ValueError`: if :obj:`default` not in :obj:`ontology`
            :obj:`ValueError`: if :obj:`default_cleaned_value` not in :obj:`ontology`
        """
        if not isinstance(ontology, pronto.Ontology):
            raise ValueError('`ontology` must be an instance of `pronto.Ontology`')
        if isinstance(terms, list):
            for term in terms:
                if not isinstance(term, pronto.term.Term) or term not in ontology:
                    raise ValueError('element {} of `terms` must be in `ontology`'.format(term))
        if default is not None and \
                (not isinstance(default, pronto.term.Term) or
                    default not in ontology or
                    (isinstance(terms, list) and default not in terms)):
            raise ValueError(
                '`default` must be `None` or in `terms`')
        if default_cleaned_value is not None and \
                (not isinstance(default_cleaned_value, pronto.term.Term) or
                    default_cleaned_value not in ontology or
                    (isinstance(terms, list) and default_cleaned_value not in terms)):
            raise ValueError(
                '`default_cleaned_value` must be `None` or in `terms`')

        super(OntologyAttribute, self).__init__(default=default,
                                                default_cleaned_value=default_cleaned_value,
                                                verbose_name=verbose_name, help=help,
                                                primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        self.ontology = ontology
        self.terms = terms
        self.none = none

    def get_default(self):
        """ Get default value for attribute

        Returns:
            :obj:`object`: initial value
        """
        return self.default

    def get_default_cleaned_value(self):
        """ Get value to replace :obj:`None` values with during cleaning

        Returns:
            :obj:`object`: initial value
        """
        return self.default_cleaned_value

    def value_equal(self, val1, val2):
        """ Determine if attribute values are equal

        Args:
            val1 (:obj:`pronto.term.Term`): first value
            val2 (:obj:`pronto.term.Term`): second value

        Returns:
            :obj:`bool`: :obj:`True` if attribute values are equal
        """
        return (not val1 and not val2) or (
            isinstance(val1, pronto.term.Term) and
            isinstance(val2, pronto.term.Term) and
            val1.id == val2.id)

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`pronto.term.Term` or :obj:`None`: cleaned value
            :obj:`core.InvalidAttribute` or :obj:`None`: cleaning error
        """
        error = None

        if value and isinstance(value, str):
            value = self.ontology.get(value.partition('!')[0].strip(), None)
            if value is None:
                error = 'Value "{}" is not in `ontology`'.format(value)

        elif value is None or value == '':
            value = self.get_default_cleaned_value()

        elif not (isinstance(value, pronto.term.Term) and value in self.ontology):
            error = "Value '{}' must be in `ontology`".format(value)

        elif isinstance(self.terms, list) and value not in self.terms:
            error = "Value '{}' must be in `terms`".format(value)

        if error:
            return (None, core.InvalidAttribute(self, [error]))
        else:
            return (value, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`pronto.term.Term`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or :obj:`None`: :obj:`None` if attribute is valid, other return list of
                errors as an instance of :obj:`core.InvalidAttribute`
        """
        if value is None:
            if not self.none:
                return core.InvalidAttribute(self, ['Value cannot be `None`'])

        elif not isinstance(value, pronto.term.Term) or value not in self.ontology:
            return core.InvalidAttribute(self, ["Value '{}' must be in `ontology`".format(value)])

        elif isinstance(self.terms, list) and value not in self.terms:
            return core.InvalidAttribute(self, ["Value '{}' must be in `terms`".format(value)])

        return None

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`object`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`object`: copy of value
        """
        return value

    def serialize(self, value):
        """ Serialize ontology instance

        Args:
            value (:obj:`pronto.term.Term`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            return value.id
        return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`pronto.term.Term`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        if value:
            return value.id
        return None

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`str`): simple Python representation of a value of the attribute

        Returns:
            :obj:`pronto.term.Term`: decoded value of the attribute
        """
        if json:
            return self.ontology[json]
        else:
            return None
