""" Attributes for references

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-20
:Copyright: 2019, Karr Lab
:License: MIT
"""

from .. import core
import re
import wc_utils.workbook.io

__all__ = [
    'Identifier',
    'IdentifierAttribute',
    'IdentifiersAttribute',
    'DoiAttribute',
    'DoisAttribute',
    'PubMedIdAttribute',
    'PubMedIdsAttribute',
]


class Identifier(object):
    """ An identifier in a namespace registered with Identifiers.org

    Attributes:
        namespace (:obj:`str`): namespace
        id (:obj:`str`): identifier in namespace
    """

    def __init__(self, namespace=None, id=None):
        """
        Args:
            namespace (:obj:`str`, optional): namespace
            id (:obj:`str`, optional): identifier in namespace
        """
        self.namespace = namespace or None
        self.id = id or None

    def to_dict(self):
        """ Get a dictionary representation

        Returns:
            :obj:`dict`: dictionary representation
        """
        return {'namespace': self.namespace, 'id': self.id}

    def from_dict(self, value):
        """ Set value from a dictionary representation

        Args:
            value (:obj:`dict`): dictionary representation

        Returns:
            :obj:`Identifier`: self
        """
        self.namespace = value['namespace']
        self.id = value['id']
        return self

    def __str__(self):
        """ Generate a string representation

        Returns:
            :obj:`str`: string representation
        """
        return "'{}' @ '{}'".format(self.id.replace("'", "\'"),
                                    self.namespace.replace("'", "\'"))

    def to_str(self):
        """ Generate a string representation (`'id' @ 'namespace'`)

        Returns:
            :obj:`str`: string representation
        """
        return str(self)

    def from_str(self, value):
        """ Set value from a string representation (`'id' @ 'namespace'`)

        Args:
            value (:obj:`value`): string representation

        Returns:
            :obj:`Identifier`: self

        Raises:
            :obj:`ValueError`: if string representation doesn't match the pattern
                `'id' @ 'namespace'`
        """
        match = re.match(r"^'((?:[^'\\]|\\.)*)' *@ *'((?:[^'\\]|\\.)*)'$", value, re.IGNORECASE)
        if not match:
            raise ValueError("Value must follow the pattern 'id' @ 'namespace'")
        self.namespace = match.group(2)
        self.id = match.group(1)
        return self

    def get_url(self):
        """ Get the URL for the webpage for the identifier

        Returns:
            :obj:`str`: URL for the webpage for the identifier
        """
        return 'https://identifiers.org/{}:{}'.format(self.namespace, self.id)


class IdentifierAttribute(core.LiteralAttribute):
    """ Identifier attribute """

    def __init__(self):
        super(IdentifierAttribute, self).__init__(default=None, none_value=None,
                                                  verbose_name='Identifier',
                                                  description=("An identifier."
                                                               "\n"
                                                               "\nExample:"
                                                               "\n  '16333295' @ 'pubmed'"),
                                                  primary=False, unique=False)
        self.type = (Identifier, None.__class__)

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): string representation of structure

        Returns:
            :obj:`Identifier`: cleaned value
            :obj:`core.InvalidAttribute`: cleaning error
        """
        if value:
            if not isinstance(value, str):
                return (None, core.InvalidAttribute(self, ['Value must be an identifier']))

            try:
                return (Identifier().from_str(value), None)
            except ValueError as err:
                return (None, core.InvalidAttribute(self, [str(err)]))
        return (None, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`Identifier`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other
                return list of errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if value is not None and not isinstance(value, Identifier):
            errors.append('Value must be an identifier')

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`Identifier`): value of attribute to validate

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
            value (:obj:`Identifier`): value of attribute to validate

        Returns:
            :obj:`list` of :obj:`int`: simple Python representation of a value of the attribute
        """
        if value:
            return value.to_dict()
        return None

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`list` of :obj:`int`): simple Python representation of a value of the attribute

        Returns:
            :obj:`Identifier`: value of attribute to validate
        """
        if json:
            return Identifier().from_dict(json)
        return None

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(IdentifierAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                           doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.any

        input_message = ['Enter an identifier.']
        error_message = ['Value must be an identifier.']

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += '\n\n'.join(error_message)

        return validation


class IdentifiersAttribute(core.LiteralAttribute):
    """ Identifiers attribute """

    def __init__(self):
        super(IdentifiersAttribute, self).__init__(default=None, none_value=None,
                                                   verbose_name='Identifiers',
                                                   description=("A list of identifiers."
                                                                "\n"
                                                                "\nExample:"
                                                                "\n  '16333295' @ 'pubmed', 'CHEBI:36927' @ 'chebi'"),
                                                   primary=False, unique=False)
        self.type = list

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): string representation of structure

        Returns:
            :obj:`Identifier`: cleaned value
            :obj:`core.InvalidAttribute`: cleaning error
        """
        if value:
            if not isinstance(value, str):
                return (None, core.InvalidAttribute(self, ['Value must be a list of identifiers']))

            id_pattern = r"'((?:[^'\\]|\\.)*)' *@ *'((?:[^'\\]|\\.)*)'"
            match = re.match(r"^{}(, *{})*$".format(id_pattern, id_pattern), value, re.IGNORECASE)
            if not match:
                return (None, core.InvalidAttribute(self, ['Value must be a list of identifiers']))

            return ([Identifier(v[1], v[0]) for v in re.findall(id_pattern, value, re.IGNORECASE)], None)
        return ([], None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`list` of :obj:`Identifier`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other
                return list of errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if not isinstance(value, list):
            errors.append('Value must be a list of identifiers')

        for v in value:
            if not isinstance(v, Identifier):
                errors.append('Value must be a list of identifiers')
                break

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`list` of :obj:`int`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        return ', '.join(str(v) for v in value)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`list` of :obj:`Identifier`): value of the attribute

        Returns:
            :obj:`list` of :obj:`int`: simple Python representation of a value of the attribute
        """
        return [v.to_dict() for v in value]

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`list` of :obj:`int`): simple Python representation of a value of the attribute

        Returns:
            :obj:`list` of :obj:`int`: decoded value of the attribute
        """
        return [Identifier().from_dict(v) for v in json]

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(IdentifiersAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                            doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.any

        input_message = ['Enter a comma-separated list of identifiers.']
        error_message = ['Value must be a comma-separated list of identifiers.']

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += '\n\n'.join(error_message)

        return validation


class DoiAttribute(core.RegexAttribute):
    """ DOI attribute """

    def __init__(self, primary=False, unique=True):
        """
        Args:
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        pattern = r'^10.\d{4,9}/[-._;()/:A-Z0-9]+$'
        super(DoiAttribute, self).__init__(pattern, re.IGNORECASE,
                                           none=True, default=None, none_value=None,
                                           verbose_name='DOI',
                                           description='Digitial Object Identifier (DOI)',
                                           primary=primary, unique=unique)

    @staticmethod
    def get_url(doi):
        """ Get the URL for a DOI

        Args:
            doi (:obj:`str`): URL for DOI
        """
        return 'https://doi.org/' + doi


class DoisAttribute(core.LiteralAttribute):
    """ DOIs attribute """

    PATTERN = r'^10.\d{4,9}\/[-._;()/:A-Z0-9]+$'

    def __init__(self):
        super(DoisAttribute, self).__init__(default=[], none_value=[],
                                            verbose_name='DOIs',
                                            description=("A list of DOIs."
                                                         "\n"
                                                         "\nExample:"
                                                         "\n  10.1016/j.mib.2015.06.004,"
                                                         " 10.1016/j.coisb.2017.10.005"),
                                            primary=False, unique=False)
        self.type = list

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): string representation of structure

        Returns:
            :obj:`list` of :obj:`int`: cleaned value
            :obj:`core.InvalidAttribute`: cleaning error
        """
        if value:
            if not isinstance(value, str):
                return (None, core.InvalidAttribute(self, ['Value must be a comma-separated list of DOIs']))

            return ([v.strip() for v in value.split(',')], None)
        return ([], None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`list` of :obj:`str`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other
                return list of errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if not isinstance(value, list):
            errors.append('Value must be a list of DOIs')

        for v in value:
            if not re.match(self.PATTERN, v, re.IGNORECASE):
                errors.append('Value must be a list of DOIs')
                break

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`list` of :obj:`int`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        return ', '.join(value)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`list` of :obj:`int`): value of the attribute

        Returns:
            :obj:`list` of :obj:`int`: simple Python representation of a value of the attribute
        """
        return value

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`list` of :obj:`int`): simple Python representation of a value of the attribute

        Returns:
            :obj:`list` of :obj:`int`: decoded value of the attribute
        """
        return json

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(DoisAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                     doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.any

        input_message = ['Enter a comma-separated list of DOIs.']
        error_message = ['Value must be a comma-separated list of DOIs.']

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += '\n\n'.join(error_message)

        return validation


class PubMedIdAttribute(core.IntegerAttribute):
    """ PubMed id attribute """

    def __init__(self, primary=False, unique=True):
        """
        Args:
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(PubMedIdAttribute, self).__init__(none=True, default=None, none_value=None, min=0,
                                                verbose_name='PubMed id',
                                                description='PubMed identifier',
                                                primary=primary, unique=unique)

    @staticmethod
    def get_url(pmid):
        """ Get the URL for a PubMed id

        Args:
            pmid (:obj:`int`): URL for PubMed id
        """
        return 'https://www.ncbi.nlm.nih.gov/pubmed/' + str(pmid)


class PubMedIdsAttribute(core.LiteralAttribute):
    """ PubMed ids attribute """

    def __init__(self):
        super(PubMedIdsAttribute, self).__init__(default=[], none_value=[],
                                                 verbose_name='PubMed ids',
                                                 description=("A list of PubMed ids."
                                                              "\n"
                                                              "\nExample:"
                                                              "\n  16333295, 16333299"),
                                                 primary=False, unique=False)
        self.type = list

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): string representation of structure

        Returns:
            :obj:`list` of :obj:`int`: cleaned value
            :obj:`core.InvalidAttribute`: cleaning error
        """
        if value:
            if not isinstance(value, str):
                return (None, core.InvalidAttribute(self, ['Value must be a string']))

            values = []
            for v in value.split(','):
                v = v.strip()
                try:
                    v_float = float(v)
                except (TypeError, ValueError):
                    return (None, core.InvalidAttribute(self, ['Value must be a comma-separated list of non-negative integers']))
                v_int = int(v_float)
                if v_int != v_float:
                    return (None, core.InvalidAttribute(self, ['Value must be a comma-separated list of non-negative integers']))
                values.append(v_int)

            return (values, None)
        return ([], None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`list` of :obj:`Identifier`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other
                return list of errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if not isinstance(value, list):
            errors.append('Value must be a list of non-negative integers')

        for v in value:
            if not isinstance(v, (int, float)) or v != int(v) or v < 0:
                errors.append('Value must be a list of non-negative integers')
                break

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`list` of :obj:`int`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        return ', '.join(str(v) for v in value)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`list` of :obj:`int`): value of the attribute

        Returns:
            :obj:`list` of :obj:`int`: simple Python representation of a value of the attribute
        """
        return value

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`list` of :obj:`int`): simple Python representation of a value of the attribute

        Returns:
            :obj:`list` of :obj:`int`: decoded value of the attribute
        """
        return json

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(PubMedIdsAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                          doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.any

        input_message = ['Enter a comma-separated list of non-negative integers.']
        error_message = ['Value must be a comma-separated list of non-negative integers.']

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += '\n\n'.join(error_message)

        return validation
