""" Chemistry attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from .. import core
from wc_utils.util import chem
from wc_utils.util.enumerate import CaseInsensitiveEnum
import wc_utils.workbook.io
import bcforms
import bpforms
import bpforms.util
import openbabel

__all__ = [
    'EmpiricalFormulaAttribute',
    'ChemicalStructure',
    'ChemicalStructureFormat',
    'ChemicalStructureAttribute',
]


class EmpiricalFormulaAttribute(core.LiteralAttribute):
    """ Empirical formula attribute """

    def __init__(self, default=None, none_value=None, verbose_name='', description="An empirical formula (e.g. 'H2O', 'CO2', or 'NaCl')",
                 primary=False, unique=False):
        """
        Args:
            default (:obj:`chem.EmpiricalFormula`, :obj:`dict`, :obj:`str`, or :obj:`None`, optional): default value
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        if not isinstance(default, chem.EmpiricalFormula) and default is not None:
            default = chem.EmpiricalFormula(default)

        super(EmpiricalFormulaAttribute, self).__init__(default=default, none_value=none_value,
                                                        verbose_name=verbose_name,
                                                        description=description,
                                                        primary=primary, unique=unique)
        if primary:
            self.type = chem.EmpiricalFormula
        else:
            self.type = (chem.EmpiricalFormula, None.__class__)

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): semantically equivalent representation

        Returns:
            :obj:`chem.EmpiricalFormula`: cleaned value
            :obj:`core.InvalidAttribute`: cleaning error
        """
        if value:
            try:
                return (chem.EmpiricalFormula(value), None)
            except ValueError as error:
                return (None, core.InvalidAttribute(self, [str(error)]))
        return (None, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`chem.EmpiricalFormula`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return
                list of errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if value is not None and not isinstance(value, chem.EmpiricalFormula):
            errors.append('Value must be an instance of `chem.EmpiricalFormula`')

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
            values (:obj:`list` of :obj:`chem.EmpiricalFormula`): list of values

        Returns:
            :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a
                list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(EmpiricalFormulaAttribute, self).validate_unique(objects, str_values)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`chem.EmpiricalFormula`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is None:
            return ''
        return str(value)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`chem.EmpiricalFormula`): value of the attribute

        Returns:
            :obj:`dict`: simple Python representation of a value of the attribute
        """
        if value:
            return dict(value)
        return None

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`dict`): simple Python representation of a value of the attribute

        Returns:
            :obj:`chem.EmpiricalFormula`: decoded value of the attribute
        """
        if json:
            return chem.EmpiricalFormula(json)
        return None

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(EmpiricalFormulaAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                                 doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.any

        input_message = ['Enter an empirical formula (e.g. "H2O").']
        error_message = ['Value must be an empirical formula (e.g. "H2O").']

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += '\n\n'.join(error_message)

        return validation


class ChemicalStructureFormat(int, CaseInsensitiveEnum):
    """ Format of a chemical structure """
    inchi = 1
    smiles = 2
    bpforms = 3
    bcforms = 4


class ChemicalStructure(object):
    """ A chemical structure

    Attributes
        value (:obj:`openbabel.OBMol`, :obj:`bpforms.BpForm`, :obj:`bcforms.BcForm`): value
        serialized_value (:obj:`str`): serialized value
        serialized_format (:obj:`ChemicalStructureFormat`): serialized format

        _value (:obj:`openbabel.OBMol`, :obj:`bpforms.BpForm`, :obj:`bcforms.BcForm`): value
        _serialized_value (:obj:`str`): serialized value
        _serialized_format (:obj:`ChemicalStructureFormat`): serialized format
    """

    def __init__(self, value=None, serialized_format=None):
        """
        Args:
            value (:obj:`str`, :obj:`openbabel.OBMol`, :obj:`bpforms.BpForm`, :obj:`bcforms.BcForm`, optional): value
            serialized_format (:obj:`ChemicalStructureFormat`, openbabel): serialized format
        """
        self._value = None
        self._serialized_format = None
        self._serialized_value = None

        self.value = value
        self.serialized_format = serialized_format or self.serialized_format

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if value is None:
            self._value = None
            self._serialized_value = None
            self._serialized_format = None

        elif isinstance(value, str):
            self.deserialize(value)

        elif isinstance(value, openbabel.OBMol):
            self._value = value
            self._serialized_value = None
            if self.serialized_format not in [ChemicalStructureFormat.inchi, ChemicalStructureFormat.smiles]:
                self._serialized_format = ChemicalStructureFormat.smiles

        elif isinstance(value, bpforms.BpForm):
            if value.alphabet not in bpforms.util.get_alphabets().values():
                raise ValueError('BpForms must use one of the defined alphabets')
            self._value = value
            self._serialized_value = None
            self._serialized_format = ChemicalStructureFormat.bpforms

        elif isinstance(value, bcforms.BcForm):
            self._value = value
            self._serialized_value = None
            self._serialized_format = ChemicalStructureFormat.bcforms

        else:
            raise ValueError('Unable to set `value` to an instance of {}'.format(
                value.__class__.__name__))

    @property
    def serialized_format(self):
        return self._serialized_format

    @serialized_format.setter
    def serialized_format(self, value):
        if value in [ChemicalStructureFormat.inchi, ChemicalStructureFormat.smiles]:
            if self._serialized_format in [ChemicalStructureFormat.inchi, ChemicalStructureFormat.smiles]:
                if value != self._serialized_format:
                    self._serialized_format = value
                    self._serialized_value = None
            else:
                raise ValueError('`serialized_format` must be consistent with `value`')
        else:
            if value != self._serialized_format:
                raise ValueError('`serialized_format` must be consistent with `value`')

    @property
    def serialized_value(self):
        return self._serialized_value

    def to_dict(self):
        """ Get a dictionary representation

        Returns:
            :obj:`dict`: dictionary representation
        """
        serialized_value = self.serialized_value
        if serialized_value is None and self.value is not None:
            if isinstance(self.value, openbabel.OBMol):
                conversion = openbabel.OBConversion()
                assert conversion.SetOutFormat(self.serialized_format.name)
                conversion.SetOptions('c', conversion.OUTOPTIONS)
                serialized_value = conversion.WriteString(self.value, True)
            else:
                serialized_value = str(self.value)
            self._serialized_value = serialized_value

        if self.serialized_format:
            serialized_format = self.serialized_format.name
            if self.serialized_format == ChemicalStructureFormat.bpforms:
                serialized_format += '/' + self.value.alphabet.id
        else:
            serialized_format = None

        return {
            "format": serialized_format,
            "value": serialized_value
        }

    def from_dict(self, dict_value):
        """ Set value from a dictionary representation

        Args:
            dict_value (:obj:`dict`): dictionary representation

        Returns:
            :obj:`ChemicalStructure`: self
        """
        format = dict_value.get('format', None)
        if format:
            serialized_format, _, serialized_alphabet = format.partition('/')
            self._serialized_format = ChemicalStructureFormat[serialized_format.strip()]
            serialized_alphabet = serialized_alphabet.strip().lower()
        else:
            self._serialized_format = None

        value = dict_value.get('value', None)
        if self.serialized_format in [ChemicalStructureFormat.inchi, ChemicalStructureFormat.smiles]:
            self._value = openbabel.OBMol()
            conversion = openbabel.OBConversion()
            assert conversion.SetInFormat(self.serialized_format.name)
            conversion.ReadString(self.value, value or '')
        elif self.serialized_format == ChemicalStructureFormat.bpforms:
            alphabet = bpforms.util.get_alphabet(serialized_alphabet)
            self._value = bpforms.BpForm(alphabet=alphabet).from_str(value or '')
        elif self.serialized_format == ChemicalStructureFormat.bcforms:
            self._value = bcforms.BcForm().from_str(value or '')
        elif self.serialized_format is None:
            if value:
                raise ValueError('`format` key must be defined')
            else:
                value = None

        self._serialized_value = value

        return self

    def serialize(self):
        """ Generate a string representation

        Returns:
            :obj:`str`: string representation
        """
        dict_value = self.to_dict()
        return '{}: {}'.format(dict_value['format'], dict_value['value'])

    def deserialize(self, serialized_value):
        """ Set value from a string representation

        Args:
            serialized_value (:obj:`str`): string representation

        Returns:
            :obj:`ChemicalStructure`: self
        """
        if serialized_value:
            serialized_format, _, serialized_value = serialized_value.partition(':')
            serialized_format = serialized_format.strip()
            serialized_value = serialized_value.strip()
        else:
            serialized_format = None
            serialized_value = None

        self.from_dict({
            'format': serialized_format,
            'value': serialized_value,
        })

        return self


class ChemicalStructureAttribute(core.LiteralAttribute):
    """ Attribute for the structures of chemical compounds """

    def __init__(self, verbose_name='',
                 description=("The InChI, SMILES-, BpForms, BcForms-encoded structure of a compound."
                              "\n"
                              "\nExamples:"
                              "\n  Small molecules (SMILES): C([N+])C([O-])=O"
                              "\n  DNA (BpForms/dna): A{m2C}GT"
                              "\n  RNA (BpForms/rna): AC{02G}U"
                              "\n  Protein (BpForms/protein): RNC{AA0037}E"
                              "\n  Complex (BcForms): 2 * subunit-A + subunit-B"),
                 primary=False, unique=False):
        """
        Args:
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(ChemicalStructureAttribute, self).__init__(default=None, none_value=None,
                                                         verbose_name=verbose_name,
                                                         description=description,
                                                         primary=primary, unique=unique)
        if primary:
            self.type = ChemicalStructure
        else:
            self.type = (ChemicalStructure, None.__class__)

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): string representation of structure

        Returns:
            :obj:`str`: cleaned value
            :obj:`core.InvalidAttribute`: cleaning error
        """
        if value:
            if isinstance(value, str):
                try:
                    return (ChemicalStructure().deserialize(value), None)
                except Exception as error:
                    return (None, core.InvalidAttribute(self, [str(error)]))

            else:
                return (None, core.InvalidAttribute(self, ['Value must be a string']))
        return (None, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`ChemicalStructure`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of
                errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if value is not None and not isinstance(value, ChemicalStructure):
            errors.append('Value must be an instance of `ChemicalStructure` or `None`')

        if self.primary and value is None:
            errors.append('{} value for primary attribute cannot be `None`'.format(
                self.__class__.__name__))

        if errors:
            return core.InvalidAttribute(self, errors)
        return None

    def validate_unique(self, objects, values):
        """ Determine if the attribute values are unique

        Args:
            objects (:obj:`list` of :obj:`Model`): list of `Model` objects
            values (:obj:`list` of :obj:`ChemicalStructure`): list of values

        Returns:
            :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a
                list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(ChemicalStructureAttribute, self).validate_unique(objects, str_values)

    def serialize(self, value):
        """ Serialize chemical structure

        Args:
            value (:obj:`ChemicalStructure`): structure

        Returns:
            :obj:`str`: string representation
        """
        if value:
            return value.serialize()
        return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`ChemicalStructure`): chemical structure

        Returns:
            :obj:`dict`: simple Python representation of a value of the attribute
        """
        if value:
            return value.to_dict()
        return None

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`dict`): simple Python representation of a value of the attribute

        Returns:
            :obj:`ChemicalStructure`: chemical structure
        """
        if json:
            return ChemicalStructure().from_dict(json)
        return None

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(ChemicalStructureAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                                  doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.any

        input_message = [
            ('Enter an InChI, SMILES-, BpForms, or BcForms-encoded structure '
             '(e.g. "[OH2]" for small molecules, "A{m2C}GT" for DNA).')]
        error_message = [
            ('Value must be an InChI, SMILES-, BpForms, or BcForms-encoded structure '
             '(e.g. "[OH2]" for small molecules, "A{m2C}GT" for DNA).')]

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += '\n\n'.join(error_message)

        return validation
