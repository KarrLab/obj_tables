""" Ontology attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-01-14
:Copyright: 2019, Karr Lab
:License: MIT
"""

from .. import core
import pronto
import types
import wc_utils.workbook.io
import wc_utils.util.ontology

__all__ = [
    'OntoTermAttribute',
]


class OntoTermAttribute(core.LiteralAttribute):
    """ Ontology attribute

    Attributes:
        ontology (:obj:`pronto.Ontology`): ontology
        namespace (:obj:`str`): prefix in term ids
        terms (:obj:`list` of :obj:`pronto.Term`): list of allowed terms. If :obj:`None`, all terms are allowed.
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
    """

    def __init__(self, ontology, namespace=None, namespace_sep=':', terms=None, none=True,
                 default=None, default_cleaned_value=None, none_value=None,
                 verbose_name='', description='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            ontology (:obj:`pronto.Ontology`): ontology
            namespace (:obj:`str`, optional): prefix in term ids
            namespace_sep (:obj:`str`, optional): namespace separator
            terms (:obj:`list` of :obj:`pronto.Term`, optional): list of allowed terms. If :obj:`None`, all terms are allowed.
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`pronto.Term`, optional): default value
            default_cleaned_value (:obj:`pronto.Term`, optional): value to replace
                :obj:`None` values with during cleaning
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
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
        if isinstance(terms, types.GeneratorType):
            terms = list(terms)
        if isinstance(terms, list):
            for term in terms:
                if not isinstance(term, pronto.Term) or term not in ontology.terms():
                    raise ValueError('element {} of `terms` must be in `ontology`'.format(term))

        if default is not None and \
                (not isinstance(default, pronto.Term)
                    or default not in ontology.terms()
                    or (isinstance(terms, list) and default not in terms)):
            raise ValueError(
                '`default` must be `None` or in `terms`')
        if default_cleaned_value is not None and \
                (not isinstance(default_cleaned_value, pronto.Term)
                    or default_cleaned_value not in ontology.terms()
                    or (isinstance(terms, list) and default_cleaned_value not in terms)):
            raise ValueError(
                '`default_cleaned_value` must be `None` or in `terms`')

        super(OntoTermAttribute, self).__init__(default=default,
                                                default_cleaned_value=default_cleaned_value, none_value=none_value,
                                                verbose_name=verbose_name, description=description,
                                                primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        if none and not primary:
            self.type = (pronto.Term, None.__class__)
        else:
            self.type = pronto.Term
        self.ontology = ontology
        self.namespace = namespace
        self.namespace_sep = namespace_sep
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

    def value_equal(self, val1, val2, tol=0.):
        """ Determine if attribute values are equal

        Args:
            val1 (:obj:`pronto.Term`): first value
            val2 (:obj:`pronto.Term`): second value
            tol (:obj:`float`, optional): equality tolerance

        Returns:
            :obj:`bool`: True if attribute values are equal
        """
        return wc_utils.util.ontology.are_terms_equivalent(val1, val2)

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`pronto.Term` or :obj:`None`: cleaned value
            :obj:`core.InvalidAttribute` or :obj:`None`: cleaning error
        """
        error = None

        if value is None or value == '':
            value = self.get_default_cleaned_value()

        elif isinstance(value, str):
            value = value.partition('!')[0].strip()

            if value and self.namespace:
                value = self.namespace + self.namespace_sep + value

            str_value = value
            value = self.ontology.get(value, str_value)
            if isinstance(value, str):
                error = 'Value "{}" is not in `ontology`'.format(value)

        elif isinstance(value, pronto.Term):
            if value not in self.ontology.terms():
                error = "Value '{}' must be in `ontology`".format(value)

        if value and isinstance(self.terms, list) and value not in self.terms:
            error = "Value '{}' must be in `terms`".format(value)

        if error:
            return (value, core.InvalidAttribute(self, [error]))
        else:
            return (value, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`pronto.Term`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or :obj:`None`: :obj:`None` if attribute is valid, other return list of
                errors as an instance of :obj:`core.InvalidAttribute`
        """
        if value is None:
            if not self.none:
                return core.InvalidAttribute(self, ['Value cannot be `None`'])
            else:
                return None

        if not isinstance(value, pronto.Term) or value not in self.ontology.terms():
            return core.InvalidAttribute(self, ["Value '{}' must be in `ontology`".format(value)])

        if isinstance(self.terms, list) and value not in self.terms:
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
            value (:obj:`pronto.Term`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value:
            if self.namespace:
                if value.id.startswith(self.namespace + self.namespace_sep):
                    return value.id[len(self.namespace) + 1:]
                else:
                    raise ValueError('Id {} must begin with namespace'.format(value.id))
            else:
                return value.id
        return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`pronto.Term`): value of the attribute

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
            :obj:`pronto.Term`: decoded value of the attribute
        """
        if json:
            return self.ontology[json]
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
        validation = super(OntoTermAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                         doc_metadata_model=doc_metadata_model)

        if self.terms is not None:
            allowed_values = [self.serialize(term) for term in self.terms]
            if len(','.join(allowed_values)) <= 255:
                validation.type = wc_utils.workbook.io.FieldValidationType.list
                validation.allowed_list_values = allowed_values

            validation.ignore_blank = self.none
            if self.none:
                input_message = ['Enter a comma-separated list of {} ontology terms "{}" or blank.'.format(
                    self.namespace, '", "'.join(allowed_values))]
                error_message = ['Value must be a comma-separated list of {} ontology terms "{}" or blank.'.format(
                    self.namespace, '", "'.join(allowed_values))]
            else:
                input_message = ['Enter a comma-separated list of {} ontology terms "{}".'.format(
                    self.namespace, '", "'.join(allowed_values))]
                error_message = ['Value must be a comma-separated list of {} ontology terms "{}".'.format(
                    self.namespace, '", "'.join(allowed_values))]

        else:
            validation.ignore_blank = self.none
            if self.none:
                input_message = ['Enter a comma-separated list of {} ontology terms or blank.'.format(
                    self.namespace)]
                error_message = ['Value must be a comma-separated list of {} ontology terms or blank.'.format(
                    self.namespace)]
            else:
                input_message = ['Enter a comma-separated list of {} ontology terms.'.format(
                    self.namespace)]
                error_message = ['Value must be a comma-separated list of {} ontology terms.'.format(
                    self.namespace)]

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default:
            input_message.append('Default: "{}".'.format(self.serialize(default)))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += '\n\n'.join(error_message)

        return validation
