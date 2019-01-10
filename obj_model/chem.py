""" Chemistry attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from . import core
from wc_utils.util import chem


class EmpiricalFormulaAttribute(core.LiteralAttribute):
    """ Empirical formula attribute """

    def __init__(self, default=None, verbose_name='', help='', primary=False, unique=False):
        """
        Args:
            default (:obj:`chem.EmpiricalFormula`, :obj:`dict`, :obj:`str`, or :obj:`None`, optional): default value
            verbose_name (:obj:`str`, optional): verbose name
            help (:obj:`str`, optional): help string
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        if not isinstance(default, chem.EmpiricalFormula) and default is not None:
            default = chem.EmpiricalFormula(default)

        super(EmpiricalFormulaAttribute, self).__init__(default=default,
                                                        verbose_name=verbose_name, help=help,
                                                        primary=primary, unique=unique)

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`str`): semantically equivalent representation

        Returns:
            :obj:`tuple` of `chem.EmpiricalFormula`, `core.InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
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
        return value.__str__()

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
