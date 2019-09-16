""" Chemistry attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from . import core
from wc_utils.util import chem
import wc_utils.workbook.io


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
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `core.InvalidAttribute`
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
           :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a list of errors as an instance of `core.InvalidAttribute`
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

    def get_excel_validation(self, sheet_models=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(EmpiricalFormulaAttribute, self).get_excel_validation(sheet_models=sheet_models)

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


class ChemicalStructureAttribute(core.LongStringAttribute):
    """ Attribute for the structures of chemical compounds """

    def __init__(self, default=None, none_value=None, verbose_name='',
                 description=("The SMILES- or BpForms-encoded structure of a chemical compound."
                              "\n"
                              "\nExamples:"
                              "\n  Small molecules (SMILES): C([N+])C([O-])=O"
                              "\n  DNA (BpForms/dna): A{m2C}GT"
                              "\n  RNA (BpForms/rna): AC{02G}U"
                              "\n  Protein (BpForms/protein): RNC{AA0037}E"),
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
        super(ChemicalStructureAttribute, self).__init__(default=default, none_value=none_value,
                                                         verbose_name=verbose_name,
                                                         description=description,
                                                         primary=primary, unique=unique)

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): string representation of structure

        Returns:
            :obj:`str`: cleaned value
            :obj:`core.InvalidAttribute`: cleaning error
        """
        if value:
            if not isinstance(value, str):
                return (None, core.InvalidAttribute(self, ['Value must be a string']))
            return (value, None)
        return (None, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`chem.EmpiricalFormula`): value of attribute to validate

        Returns:
            :obj:`core.InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `core.InvalidAttribute`
        """
        errors = []

        if value and not isinstance(value, str):
            errors.append('Value must be a string or None')

        if not value and value is not None:
            errors.append('Value must be a string or None')

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
           :obj:`core.InvalidAttribute` or None: None if values are unique, otherwise return a list of errors as an instance of `core.InvalidAttribute`
        """
        str_values = []
        for v in values:
            str_values.append(self.serialize(v))
        return super(ChemicalStructureAttribute, self).validate_unique(objects, str_values)

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`chem.EmpiricalFormula`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is None:
            return ''
        return value

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`chem.EmpiricalFormula`): value of the attribute

        Returns:
            :obj:`dict`: simple Python representation of a value of the attribute
        """
        if value:
            return value
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
            return json
        return None

    def get_excel_validation(self, sheet_models=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(ChemicalStructureAttribute, self).get_excel_validation(sheet_models=sheet_models)

        validation.type = wc_utils.workbook.io.FieldValidationType.any

        input_message = ['Enter a SMILES- or BpForms-encoded structure (e.g. "[OH2]" for small molecules, "A{m2C}GT" for DNA).']
        error_message = ['Value must be a SMILES- or BpForms-encoded structure (e.g. "[OH2]" for small molecules, "A{m2C}GT" for DNA).']

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
