""" Utilities for processing mathematical expressions used by obj_tables models

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2018-12-19
:Copyright: 2016-2019, Karr Lab
:License: MIT
"""
import collections
import math
import pint  # noqa: F401
import re
import token
import tokenize
import types  # noqa: F401
from enum import Enum
from io import BytesIO
from obj_tables.core import (Model, RelatedAttribute, OneToOneAttribute, ManyToOneAttribute,
                             InvalidObject, InvalidAttribute)
from wc_utils.util.misc import DFSMAcceptor

__all__ = [
    'OneToOneExpressionAttribute',
    'ManyToOneExpressionAttribute',
]


class ObjTablesTokenCodes(int, Enum):
    """ ObjTablesToken codes used in parsed expressions """
    obj_id = 1
    math_func_id = 2
    number = 3
    op = 4
    other = 5


# a matched token pattern used by tokenize
IdMatch = collections.namedtuple('IdMatch', 'model_type, token_pattern, match_string')
IdMatch.__doc__ += ': Matched token pattern used by tokenize'
IdMatch.model_type.__doc__ = 'The type of Model matched'
IdMatch.token_pattern.__doc__ = 'The token pattern used by the match'
IdMatch.match_string.__doc__ = 'The matched string'


# a token in a parsed expression, returned in a list by tokenize
ObjTablesToken = collections.namedtuple('ObjTablesToken', 'code, token_string, model_type, model_id, model')
# make model_type, model_id, and model optional: see https://stackoverflow.com/a/18348004
ObjTablesToken.__new__.__defaults__ = (None, None, None)
ObjTablesToken.__doc__ += ': ObjTablesToken in a parsed obj_tables expression'
ObjTablesToken.code.__doc__ = 'ObjTablesTokenCodes encoding'
ObjTablesToken.token_string.__doc__ = "The token's string"
ObjTablesToken.model_type.__doc__ = "When code is obj_id, the obj_tables obj's type"
ObjTablesToken.model_id.__doc__ = "When code is obj_id, the obj_tables obj's id"
ObjTablesToken.model.__doc__ = "When code is obj_id, the obj_tables obj"


# container for an unambiguous Model id
LexMatch = collections.namedtuple('LexMatch', 'obj_tables_tokens, num_py_tokens')
LexMatch.__doc__ += ': container for an unambiguous Model id'
LexMatch.obj_tables_tokens.__doc__ = "List of ObjTablesToken's created"
LexMatch.num_py_tokens.__doc__ = 'Number of Python tokens consumed'


class OneToOneExpressionAttribute(OneToOneAttribute):
    """ Expression one-to-one attribute """

    def serialize(self, expression, encoded=None):
        """ Serialize related object

        Args:
            expression (:obj:`obj_tables.Model`): the referenced `Expression`
            encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

        Returns:
            :obj:`str`: simple Python representation
        """
        if expression:
            return expression.serialize()
        else:
            return ''

    def deserialize(self, value, objects, decoded=None):
        """ Deserialize value

        Args:
            value (:obj:`str`): String representation
            objects (:obj:`dict`): dictionary of objects, grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value:
            return self.related_class.deserialize(value, objects)
        return (None, None)

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(OneToOneAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                         doc_metadata_model=doc_metadata_model)

        if self.related_class.Meta.expression_is_linear:
            type = 'linear '
        else:
            type = ''

        terms = []
        for attr in self.related_class.Meta.attributes.values():
            if isinstance(attr, RelatedAttribute) and \
                    attr.related_class.__name__ in self.related_class.Meta.expression_term_models:
                terms.append(attr.related_class.Meta.verbose_name_plural)
        if terms:
            if len(terms) == 1:
                terms = terms[0]
            else:
                terms = '{} and {}'.format(', '.join(terms[0:-1]), terms[-1])

            input_message = 'Enter a {}expression of {}.'.format(type, terms)
            error_message = 'Value must be a {}expression of {}.'.format(type, terms)
        else:
            input_message = 'Enter a {}expression.'.format(type, terms)
            error_message = 'Value must be a {}expression.'.format(type, terms)

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += input_message

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += error_message

        return validation


class ManyToOneExpressionAttribute(ManyToOneAttribute):
    """ Expression many-to-one attribute """

    def serialize(self, expression, encoded=None):
        """ Serialize related object

        Args:
            expression (:obj:`Expression`): the related `Expression`
            encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

        Returns:
            :obj:`str`: simple Python representation of the rate law expression
        """
        if expression:
            return expression.serialize()
        else:
            return ''

    def deserialize(self, value, objects, decoded=None):
        """ Deserialize value

        Args:
            value (:obj:`str`): String representation
            objects (:obj:`dict`): dictionary of objects, grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value:
            return self.related_class.deserialize(value, objects)
        return (None, None)

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(ManyToOneAttribute, self).get_excel_validation(sheet_models=sheet_models,
                                                                          doc_metadata_model=doc_metadata_model)

        if self.related_class.Meta.expression_is_linear:
            type = 'linear '
        else:
            type = ''

        terms = []
        for attr in self.related_class.Meta.attributes.values():
            if isinstance(attr, RelatedAttribute) and \
                    attr.related_class.__name__ in self.related_class.Meta.expression_term_models:
                terms.append(attr.related_class.Meta.verbose_name_plural)
        if terms:
            if len(terms) == 1:
                terms = terms[0]
            else:
                terms = '{} and {}'.format(', '.join(terms[0:-1]), terms[-1])

            input_message = 'Enter a {}expression of {}.'.format(type, terms)
            error_message = 'Value must be a {}expression of {}.'.format(type, terms)
        else:
            input_message = 'Enter a {}expression.'.format(type, terms)
            error_message = 'Value must be a {}expression.'.format(type, terms)

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message += input_message

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message += error_message

        return validation


class ExpressionTermMeta(object):
    """ Metadata for subclasses that can appear in expressions

    Attributes:
        expression_term_token_pattern (:obj:`tuple`): token pattern for the name of the
            term in expression
        expression_term_units (:obj:`str`): name of attribute which describes the units
            of the expression term
    """
    expression_term_token_pattern = (token.NAME, )
    expression_term_units = 'units'


class ExpressionStaticTermMeta(ExpressionTermMeta):
    """ Metadata for subclasses with static values that can appear in expressions

    Attributes:
        expression_term_value (:obj:`str`): name of attribute which encodes the value of
            the term
    """
    expression_term_value = 'value'


class ExpressionDynamicTermMeta(ExpressionTermMeta):
    """ Metadata for subclasses with dynamic values that can appear in expressions """
    pass


class ExpressionExpressionTermMeta(ExpressionTermMeta):
    """ Metadata for subclasses with expressions that can appear in expressions

    Attributes:
        expression_term_model (:obj:`str`): name of attribute which encodes the expression for
            the term
    """
    expression_term_model = None


class Expression(object):
    """ Generic methods for mathematical expressions

    Attributes:
        _parsed_expression (:obj:`ParsedExpression`): parsed expression
    """

    class Meta(object):
        """ Metadata for subclasses of :obj:`Expression`

        Attributes:
            expression_term_models (:obj:`tuple` of :obj:`str`): names of classes
                which can appear as terms in the expression
            expression_valid_functions (:obj:`tuple` of :obj:`types.FunctionType`): Python
                functions which can appear in the expression
            expression_is_linear (:obj:`bool`): if :obj:`True`, validate that the expression is linear
            expression_type (:obj:`type`): type of the expression
            expression_unit_registry (:obj:`pint.UnitRegistry`): unit registry
        """
        expression_term_models = ()
        expression_valid_functions = (
            float,

            math.fabs,
            math.ceil,
            math.floor,
            round,

            math.exp,
            math.expm1,
            math.pow,
            math.sqrt,
            math.log,
            math.log1p,
            math.log10,
            math.log2,

            math.factorial,

            math.sin,
            math.cos,
            math.tan,
            math.acos,
            math.asin,
            math.atan,
            math.atan2,
            math.hypot,

            math.degrees,
            math.radians,

            min,
            max)
        expression_is_linear = False
        expression_type = None
        expression_unit_registry = None

    def serialize(self):
        """ Generate string representation

        Returns:
            :obj:`str`: value of primary attribute
        """
        return self.expression

    @classmethod
    def deserialize(cls, model_cls, value, objects):
        """ Deserialize `value` into an `Expression`

        Args:
            model_cls (:obj:`type`): `Expression` class or subclass
            value (:obj:`str`): string representation of the mathematical expression, in a
                Python expression
            objects (:obj:`dict`): dictionary of objects which can be used in `expression`, grouped by model

        Returns:
            :obj:`tuple`: on error return (:obj:`None`, :obj:`InvalidAttribute`),
                otherwise return (object in this class with instantiated `_parsed_expression`, `None`)
        """
        value = value or ''

        expr_field = 'expression'
        try:
            parsed_expression = ParsedExpression(model_cls, expr_field, value, objects)
        except ParsedExpressionError as e:
            attr = model_cls.Meta.attributes['expression']
            return (None, InvalidAttribute(attr, [str(e)]))
        _, used_objects, errors = parsed_expression.tokenize()
        if errors:
            attr = model_cls.Meta.attributes['expression']
            return (None, InvalidAttribute(attr, errors))
        if model_cls not in objects:
            objects[model_cls] = {}
        if value in objects[model_cls]:
            obj = objects[model_cls][value]
        else:
            obj = model_cls(expression=value)
            objects[model_cls][value] = obj

            for attr_name, attr in model_cls.Meta.attributes.items():
                if isinstance(attr, RelatedAttribute) and \
                        attr.related_class.__name__ in model_cls.Meta.expression_term_models:
                    attr_value = list(used_objects.get(attr.related_class, {}).values())
                    setattr(obj, attr_name, attr_value)
        obj._parsed_expression = parsed_expression

        # check expression is linear
        parsed_expression.is_linear, _ = LinearParsedExpressionValidator().validate(parsed_expression)
        cls.set_lin_coeffs(obj)

        return (obj, None)

    @classmethod
    def set_lin_coeffs(cls, obj):
        """ Set the linear coefficients for the related objects

        Args:
            obj (:obj:`Model`): `Expression` object
        """
        model_cls = obj.__class__
        parsed_expr = obj._parsed_expression
        obj_tables_tokens = parsed_expr._obj_tables_tokens
        is_linear = parsed_expr.is_linear

        if is_linear:
            default_val = 0.
        else:
            default_val = float('nan')

        parsed_expr.lin_coeffs = lin_coeffs = {}
        for attr_name, attr in model_cls.Meta.attributes.items():
            if isinstance(attr, RelatedAttribute) and \
                    attr.related_class.__name__ in model_cls.Meta.expression_term_models:
                lin_coeffs[attr.related_class] = {}

        for related_class, related_objs in parsed_expr.related_objects.items():
            for related_obj in related_objs.values():
                lin_coeffs[related_class][related_obj] = default_val

        if not is_linear:
            return

        sense = 1.
        cur_coeff = 1.
        for obj_table_token in obj_tables_tokens:
            if obj_table_token.code == ObjTablesTokenCodes.op and obj_table_token.token_string == '+':
                sense = 1.
                cur_coeff = 1.
            elif obj_table_token.code == ObjTablesTokenCodes.op and obj_table_token.token_string == '-':
                sense = -1.
                cur_coeff = 1.
            elif obj_table_token.code == ObjTablesTokenCodes.number:
                cur_coeff = float(obj_table_token.token_string)
            elif obj_table_token.code == ObjTablesTokenCodes.obj_id:
                lin_coeffs[obj_table_token.model_type][obj_table_token.model] += sense * cur_coeff

    @classmethod
    def validate(cls, model_obj, parent_obj):
        """ Determine whether an expression model is valid

        One check eval's its deserialized expression

        Args:
            model_obj (:obj:`Expression`): expression object
            parent_obj (:obj:`Model`): parent of expression object

        Returns:
            :obj:`InvalidObject` or None: `None` if the object is valid,
                otherwise return a list of errors in an :obj:`InvalidObject` instance
        """
        model_cls = model_obj.__class__

        # generate _parsed_expression
        objs = {}
        for related_attr_name, related_attr in model_cls.Meta.attributes.items():
            if isinstance(related_attr, RelatedAttribute):
                objs[related_attr.related_class] = {
                    m.get_primary_attribute(): m for m in getattr(model_obj, related_attr_name)
                }
        try:
            model_obj._parsed_expression = ParsedExpression(model_obj.__class__, 'expression',
                                                            model_obj.expression, objs)
        except ParsedExpressionError as e:
            attr = model_cls.Meta.attributes['expression']
            attr_err = InvalidAttribute(attr, [str(e)])
            return InvalidObject(model_obj, [attr_err])

        is_valid, _, errors = model_obj._parsed_expression.tokenize()
        if is_valid is None:
            attr = model_cls.Meta.attributes['expression']
            attr_err = InvalidAttribute(attr, errors)
            return InvalidObject(model_obj, [attr_err])
        model_obj._parsed_expression.is_linear, _ = LinearParsedExpressionValidator().validate(
            model_obj._parsed_expression)
        cls.set_lin_coeffs(model_obj)

        # check that related objects match the tokens of the _parsed_expression
        related_objs = {}
        for related_attr_name, related_attr in model_cls.Meta.attributes.items():
            if isinstance(related_attr, RelatedAttribute):
                related_model_objs = getattr(model_obj, related_attr_name)
                if related_model_objs:
                    related_objs[related_attr.related_class] = set(related_model_objs)

        token_objs = {}
        token_obj_ids = {}
        for obj_table_token in model_obj._parsed_expression._obj_tables_tokens:
            if obj_table_token.model_type is not None:
                if obj_table_token.model_type not in token_objs:
                    token_objs[obj_table_token.model_type] = set()
                    token_obj_ids[obj_table_token.model_type] = set()
                token_objs[obj_table_token.model_type].add(obj_table_token.model)
                token_obj_ids[obj_table_token.model_type].add(obj_table_token.token_string)

        if related_objs != token_objs:
            attr = model_cls.Meta.attributes['expression']
            attr_err = InvalidAttribute(attr, ['Related objects must match the tokens of the analyzed expression'])
            return InvalidObject(model_obj, [attr_err])

        # check that expression is valid
        try:
            rv = model_obj._parsed_expression.test_eval()
            if model_obj.Meta.expression_type:
                if not isinstance(rv, model_obj.Meta.expression_type):
                    attr = model_cls.Meta.attributes['expression']
                    attr_err = InvalidAttribute(attr,
                                                ["Evaluating '{}', a {} expression, should return a {} but it returns a {}".format(
                                                    model_obj.expression, model_obj.__class__.__name__,
                                                    model_obj.Meta.expression_type.__name__, type(rv).__name__)])
                    return InvalidObject(model_obj, [attr_err])
        except ParsedExpressionError as e:
            attr = model_cls.Meta.attributes['expression']
            attr_err = InvalidAttribute(attr, [str(e)])
            return InvalidObject(model_obj, [attr_err])

        # check expression is linear
        if model_obj.Meta.expression_is_linear and not model_obj._parsed_expression.is_linear:
            attr = model_cls.Meta.attributes['expression']
            attr_err = InvalidAttribute(attr, ['Expression must be linear in species counts'])
            return InvalidObject(model_obj, [attr_err])

        # return `None` to indicate valid object
        return None

    @staticmethod
    def make_expression_obj(model_type, expression, objs):
        """ Make an expression object

        Args:
            model_type (:obj:`type`): an :obj:`Model` that uses a mathemetical expression, like
                `Function` and `Observable`
            expression (:obj:`str`): the expression used by the `model_type` being created
            objs (:obj:`dict` of `dict`): all objects that are referenced in `expression`

        Returns:
            :obj:`tuple`: if successful, (:obj:`Model`, :obj:`None`) containing a new instance of
                `model_type`'s expression helper class; otherwise, (:obj:`None`, :obj:`InvalidAttribute`)
                reporting the error
        """
        expr_model_type = model_type.Meta.expression_term_model
        return expr_model_type.deserialize(expression, objs)

    @classmethod
    def make_obj(cls, model, model_type, primary_attr, expression, objs, allow_invalid_objects=False):
        """ Make a model that contains an expression by using its expression helper class

        For example, this uses `FunctionExpression` to make a `Function`.

        Args:
            model (:obj:`Model`): an instance of :obj:`Model` which is the root model
            model_type (:obj:`type`): a subclass of :obj:`Model` that uses a mathemetical expression, like
                `Function` and `Observable`
            primary_attr (:obj:`object`): the primary attribute of the `model_type` being created
            expression (:obj:`str`): the expression used by the `model_type` being created
            objs (:obj:`dict` of `dict`): all objects that are referenced in `expression`
            allow_invalid_objects (:obj:`bool`, optional): if set, return object - not error - if
                the expression object does not validate

        Returns:
            :obj:`Model` or :obj:`InvalidAttribute`: a new instance of `model_type`, or,
                if an error occurs, an :obj:`InvalidAttribute` reporting the error
        """
        expr_model_obj, error = cls.make_expression_obj(model_type, expression, objs)
        if error:
            return error
        error_or_none = expr_model_obj.validate()
        if error_or_none is not None and not allow_invalid_objects:
            return error_or_none
        related_name = model_type.Meta.attributes['model'].related_name
        related_in_model = getattr(model, related_name)
        new_obj = related_in_model.create(expression=expr_model_obj)
        setattr(new_obj, model_type.Meta.primary_attribute.name, primary_attr)
        return new_obj

    def merge_attrs(self, other, other_objs_in_self, self_objs_in_other):
        """ Merge attributes of two objects

        Args:
            other (:obj:`Model`): other model
            other_objs_in_self (:obj:`dict`): dictionary that maps instances of objects in another model to objects
                in a model
            self_objs_in_other (:obj:`dict`): dictionary that maps instances of objects in a model to objects
                in another model
        """
        for cls, other_related_objs in other._parsed_expression.related_objects.items():
            for obj_id, other_obj in other_related_objs.items():
                self._parsed_expression.related_objects[cls][obj_id] = other_objs_in_self.get(other_obj, other_obj)


class ParsedExpressionError(Exception):
    """ Exception raised for errors in `ParsedExpression`

    Attributes:
        message (:obj:`str`): the exception's message
    """

    def __init__(self, message=None):
        """
        Args:
            message (:obj:`str`, optional): the exception's message
        """
        super().__init__(message)


class ParsedExpression(object):
    """ An expression in an :obj:`obj_tables` :obj:`Model`

    These expressions are limited Python expressions with specific semantics:

    * They must be syntactically correct Python, except that an identifier can begin with numerical digits.
    * No Python keywords, strings, or tokens that do not belong in expressions are allowed.
    * All Python identifiers must be the primary attribute of an :obj:`obj_tables` object or the name of a
      function in the :obj:`math` package. Objects in the model
      are provided in :obj:`_objs`, and the allowed subset of functions in :obj:`math` must be provided in an
      iterator in the :obj:`expression_valid_functions` attribute of the :obj:`Meta` class of a model whose whose expression
      is being processed.
    * Currently (July, 2018), an identifier may refer to a :obj:`Species`, :obj:`Parameter`, :obj:`Observable`,
      :obj:`Reaction`, :obj:`Observable` or :obj:`DfbaObjReaction`.
    * Cycles of references are illegal.
    * An identifier must unambiguously refer to exactly one related :obj:`Model` in a model.
    * Each :obj:`Model` that can be used in an expression must have an ID that is an identifier,
      or define :obj:`expression_term_token_pattern` as an attribute that describes the :obj:`Model`\ 's
      syntactic Python structure. See :obj:`Species` for an example.
    * Every expression must be computable at any time during a simulation. The evaluation of an expression
      always occurs at a precise simulation time, which is implied by the expression but not explicitly
      represented. E.g., a reference to a :obj:`Species` means its concentration at the time the expression is
      `eval`\ ed. These are the meanings of references:

      * :obj:`Species`: its current concentration
      * :obj:`Parameter`: its value, which is static
      * :obj:`Observable`: its current value, whose units depend on its definition
      * :obj:`Reaction`: its current flux
      * :obj:`DfbaObjReaction`: its current flux

    The modeller is responsible for ensuring that units in expressions are internally consistent and appropriate
    for the expression's use.

    Attributes:
        model_cls (:obj:`type`): the :obj:`Model` which has an expression
        attr (:obj:`str`): the attribute name of the expression in :obj:`model_cls`
        expression (:obj:`str`): the expression defined in the obj_tables :obj:`Model`
        _py_tokens (:obj:`list` of :obj:`collections.namedtuple`): a list of Python tokens generated by `tokenize.tokenize()`
        _objs (:obj:`dict`): dict of obj_tables Models that might be referenced in :obj:`expression`;
            maps model type to a dict mapping ids to Model instances
        valid_functions (:obj:`set`): the union of all :obj:`valid_functions` attributes for :obj:`_objs`
        unit_registry (:obj:`pint.UnitRegistry`): unit registry
        related_objects (:obj:`dict`): models that are referenced in :obj:`expression`; maps model type to
            dict that maps model id to model instance
        lin_coeffs (:obj:`dict`): linear coefficients of models that are referenced in :obj:`expression`;
            maps model type to dict that maps models to coefficients
        errors (:obj:`list` of :obj:`str`): errors found when parsing an :obj:`expression` fails
        _obj_tables_tokens (:obj:`list` of :obj:`ObjTablesToken`): tokens obtained when an :obj:`expression`
            is successfully `tokenize`\ d; if empty, then this :obj:`ParsedExpression` cannot use :obj:`eval`
        _compiled_expression (:obj:`str`): compiled expression that can be evaluated by :obj:`eval`
        _compiled_expression_with_units (:obj:`str`): compiled expression with units that can be evaluated by :obj:`eval`
        _compiled_namespace (:obj:`dict`): compiled namespace for evaluation by :obj:`eval`
        _compiled_namespace_with_units (:obj:`dict`): compiled namespace with units for evaluation by :obj:`eval`
    """

    # ModelType.model_id
    MODEL_TYPE_DISAMBIG_PATTERN = (token.NAME, token.DOT, token.NAME)
    FUNC_PATTERN = (token.NAME, token.LPAR)

    # enumerate and detect Python tokens that are legal in obj_tables expressions
    LEGAL_TOKENS_NAMES = (
        'NUMBER',  # number
        'NAME',  # variable names
        'LSQB', 'RSQB',  # for compartment names
        'DOT',  # for disambiguating variable types
        'COMMA',  # for function arguments
        'DOUBLESTAR', 'MINUS', 'PLUS', 'SLASH', 'STAR',  # mathematical operators
        'LPAR', 'RPAR',  # for mathematical grouping
        'EQEQUAL', 'GREATER', 'GREATEREQUAL', 'LESS', 'LESSEQUAL', 'NOTEQUAL',  # comparison operators
    )
    LEGAL_TOKENS = set()
    for legal_token_name in LEGAL_TOKENS_NAMES:
        legal_token = getattr(token, legal_token_name)
        LEGAL_TOKENS.add(legal_token)

    def __init__(self, model_cls, attr, expression, objs):
        """ Create an instance of ParsedExpression

        Args:
            model_cls (:obj:`type`): the :obj:`Model` which has an expression
            attr (:obj:`str`): the attribute name of the expression in `model_cls`
            expression (:obj:`obj`): the expression defined in the obj_tables :obj:`Model`
            objs (:obj:`dict`): dictionary of model objects (instances of :obj:`Model`) organized
                by their type

        Raises:
            :obj:`ParsedExpressionError`: if `model_cls` is not a subclass of :obj:`Model`,
                or lexical analysis of `expression` raises an exception,
                or `objs` includes model types that `model_cls` should not reference
        """
        if not issubclass(model_cls, Model):
            raise ParsedExpressionError("model_cls '{}' is not a subclass of Model".format(
                model_cls.__name__))
        if not hasattr(model_cls.Meta, 'expression_term_models'):
            raise ParsedExpressionError("model_cls '{}' doesn't have a 'Meta.expression_term_models' attribute".format(
                model_cls.__name__))
        self.term_models = set()
        for expression_term_model_type_name in model_cls.Meta.expression_term_models:
            related_class = None
            for attr in model_cls.Meta.attributes.values():
                if isinstance(attr, RelatedAttribute) \
                        and attr.related_class.__name__ == expression_term_model_type_name:
                    related_class = attr.related_class
                    break
            if related_class:
                self.term_models.add(related_class)
            else:
                raise ParsedExpressionError('Expression term {} must have a relationship to {}'.format(
                    expression_term_model_type_name, model_cls.__name__))
        self.valid_functions = set()
        if hasattr(model_cls.Meta, 'expression_valid_functions'):
            self.valid_functions.update(model_cls.Meta.expression_valid_functions)

        self.unit_registry = model_cls.Meta.expression_unit_registry

        self._objs = objs
        self.model_cls = model_cls
        self.attr = attr
        if isinstance(expression, int) or isinstance(expression, float):
            expression = str(expression)
        if not isinstance(expression, str):
            raise ParsedExpressionError(f"Expression '{expression}' in {model_cls.__name__} must be "
                                        "string, float or integer")
        # strip leading and trailing whitespace from expression, which would create a bad token error
        self.expression = expression.strip()

        # allow identifiers that start with a number
        expr = self.__prep_expr_for_tokenization(self.expression)

        try:
            g = tokenize.tokenize(BytesIO(expr.encode('utf-8')).readline)
            # strip the leading ENCODING token and trailing NEWLINE and ENDMARKER tokens
            self._py_tokens = list(g)[1:-1]
            if self._py_tokens and self._py_tokens[-1].type == token.NEWLINE:
                self._py_tokens = self._py_tokens[:-1]
        except tokenize.TokenError as e:
            raise ParsedExpressionError("parsing '{}', a {}.{}, creates a Python syntax error: '{}'".format(
                self.expression, self.model_cls.__name__, self.attr, str(e)))

        self.__reset_tokenization()

    @staticmethod
    def __prep_expr_for_tokenization(expr):
        """ Prepare an expression for tokenization with the Python tokenizer

        * Add prefix ("__digit__") to names (identifiers of obj_tables objects) that begin with a number

        Args:
            expr (:obj:`str`): expression

        Returns:
            :obj:`str`: prepared expression
        """
        return re.sub(r'(^|\b)'
                      # ignore tokens which are regular, exponential, and hexidecimal numbers
                      r'(?!((0[x][0-9a-f]+(\b|$))|([0-9]+e[\-\+]?[0-9]+(\b|$))))'
                      r'([0-9]+[a-z_][0-9a-z_]*)'
                      r'(\b|$)',
                      r'__digit__\7', expr, flags=re.I)

    def __reset_tokenization(self):
        """ Reset tokenization
        """
        self.related_objects = {}
        self.lin_coeffs = {}
        for model_type in self.term_models:
            self.related_objects[model_type] = {}
            self.lin_coeffs[model_type] = {}

        self.errors = []
        self._obj_tables_tokens = []
        self._compiled_expression = ''
        self._compiled_expression_with_units = ''
        self._compiled_namespace = {}
        self._compiled_namespace_with_units = {}

    def _get_trailing_whitespace(self, idx):
        """ Get the number of trailing spaces following a Python token

        Args:
            idx (:obj:`int`): index of the token in `self._py_tokens`
        """
        if len(self._py_tokens) - 1 <= idx:
            return 0
        # get distance between the next token's start column and end column of the token at idx
        # assumes that an expression uses only one line
        return self._py_tokens[idx + 1].start[1] - self._py_tokens[idx].end[1]

    def recreate_whitespace(self, expr):
        """ Insert the whitespace in this object's `expression` into an expression with the same token count

        Used to migrate an expression to a different set of model type names.

        Args:
            expr (:obj:`str`): a syntactically correct Python expression

        Returns:
            :obj:`str`: `expr` with the whitespace in this instance's `expression` inserted between
                its Python tokens

        Raises:
            :obj:`ParsedExpressionError`: if tokenizing `expr` raises an exception,
                or if `expr` doesn't have the same number of Python tokens as `self.expression`
        """
        prepped_expr = self.__prep_expr_for_tokenization(expr)
        try:
            g = tokenize.tokenize(BytesIO(prepped_expr.encode('utf-8')).readline)
            # strip the leading ENCODING marker and trailing NEWLINE and ENDMARKER tokens
            tokens = list(g)[1:-1]
            if tokens and tokens[-1].type == token.NEWLINE:
                tokens = tokens[:-1]
        except tokenize.TokenError as e:
            raise ParsedExpressionError("parsing '{}' creates a Python syntax error: '{}'".format(
                expr, str(e)))
        if len(tokens) != len(self._py_tokens):
            raise ParsedExpressionError("can't recreate whitespace in '{}', as it has {} instead "
                                        "of {} tokens expected".format(expr, len(tokens), len(self._py_tokens)))

        expanded_expr = []
        for i_tok, tok in enumerate(tokens):
            if tok.type == token.NAME and tok.string.startswith('__digit__'):
                expanded_expr.append(tok.string[9:])
            else:
                expanded_expr.append(tok.string)
            ws = ' ' * self._get_trailing_whitespace(i_tok)
            expanded_expr.append(ws)
        return ''.join(expanded_expr)

    def _get_model_type(self, name):
        """ Find the `obj_tables` model type corresponding to `name`

        Args:
            name (:obj:`str`): the name of a purported `obj_tables` model type in an expression

        Returns:
            :obj:`object`: `None` if no model named `name` exists in `self.term_models`,
                else the type of the model with that name
        """
        for model_type in self.term_models:
            if name == model_type.__name__:
                return model_type
        return None

    def _match_tokens(self, token_pattern, idx):
        """ Indicate whether `tokens` begins with a pattern of tokens that match `token_pattern`

        Args:
            token_pattern (:obj:`tuple` of :obj:`int`): a tuple of Python token numbers, taken from the
            `token` module
            idx (:obj:`int`): current index into `tokens`

        Returns:
            :obj:`object`: :obj:`bool`, False if the initial elements of `tokens` do not match the
            syntax in `token_pattern`, or :obj:`str`, the matching string
        """
        if not token_pattern:
            return False
        if len(self._py_tokens) - idx < len(token_pattern):
            return False
        for tok_idx, token_pat_num in enumerate(token_pattern):
            if self._py_tokens[idx + tok_idx].exact_type != token_pat_num:
                return False
            # because a obj_tables primary attribute shouldn't contain white space, do not allow it between the self._py_tokens
            # that match token_pattern
            if 0 < tok_idx and self._py_tokens[idx + tok_idx - 1].end != self._py_tokens[idx + tok_idx].start:
                return False

        match_val = ''
        for tok in self._py_tokens[idx:idx + len(token_pattern)]:
            if tok.type == token.NAME and tok.string.startswith('__digit__'):
                match_val += tok.string[9:]
            else:
                match_val += tok.string
        return match_val

    def _get_disambiguated_id(self, idx, case_fold_match=False):
        """ Try to parse a disambiguated `obj_tables` id from `self._py_tokens` at `idx`

        Look for a disambugated id (a Model written as `ModelType.model_id`). If tokens do not match,
        return `None`. If tokens match, but their values are wrong, return an error `str`.
        If a disambugated id is found, return a `LexMatch` describing it.

        Args:
            idx (:obj:`int`): current index into `tokens`
            case_fold_match (:obj:`bool`, optional): if set, `casefold()` identifiers before matching;
                in a `ObjTablesToken`, `token_string` retains the original expression text, while `model_id`
                contains the casefold'ed value; identifier keys in `self._objs` must already be casefold'ed;
                default=False

        Returns:
            :obj:`object`: If tokens do not match, return `None`. If tokens match,
                but their values are wrong, return an error `str`.
                If a disambugated id is found, return a `LexMatch` describing it.
        """
        disambig_model_match = self._match_tokens(self.MODEL_TYPE_DISAMBIG_PATTERN, idx)
        if disambig_model_match:
            disambig_model_type = self._py_tokens[idx].string
            possible_model_id = self._py_tokens[idx + 2].string
            if case_fold_match:
                possible_model_id = possible_model_id.casefold()

            # the disambiguation model type must be in self.term_models
            model_type = self._get_model_type(disambig_model_type)
            if model_type is None:
                return ("'{}', a {}.{}, contains '{}', but the disambiguation model type '{}' "
                        "cannot be referenced by '{}' expressions".format(
                            self.expression, self.model_cls.__name__,
                            self.attr, disambig_model_match, disambig_model_type,
                            self.model_cls.__name__))

            if possible_model_id not in self._objs.get(model_type, {}):
                return "'{}', a {}.{}, contains '{}', but '{}' is not the id of a '{}'".format(
                    self.expression, self.model_cls.__name__, self.attr, disambig_model_match,
                    possible_model_id, disambig_model_type)

            return LexMatch([ObjTablesToken(ObjTablesTokenCodes.obj_id, disambig_model_match, model_type,
                                            possible_model_id, self._objs[model_type][possible_model_id])],
                            len(self.MODEL_TYPE_DISAMBIG_PATTERN))

        # no match
        return None

    def _get_related_obj_id(self, idx, case_fold_match=False):
        """ Try to parse a related object `obj_tables` id from `self._py_tokens` at `idx`

        Different `obj_tables` objects match different Python token patterns. The default pattern
        is (token.NAME, ), but an object of type `model_type` can define a custom pattern in
        `model_type.Meta.expression_term_token_pattern`, as `Species` does. Some patterns may consume
            multiple Python tokens.

        Args:
            idx (:obj:`int`): current index into `_py_tokens`
            case_fold_match (:obj:`bool`, optional): if set, casefold identifiers before matching;
                identifier keys in `self._objs` must already be casefold'ed; default=False

        Returns:
            :obj:`object`: If tokens do not match, return `None`. If tokens match,
                but their values are wrong, return an error `str`.
                If a related object id is found, return a `LexMatch` describing it.
        """
        token_matches = set()
        id_matches = set()
        for model_type in self.term_models:
            token_pattern = model_type.Meta.expression_term_token_pattern
            match_string = self._match_tokens(token_pattern, idx)
            if match_string:
                token_matches.add(match_string)
                # is match_string the ID of an instance in model_type?
                if case_fold_match:
                    if match_string.casefold() in self._objs.get(model_type, {}):
                        id_matches.add(IdMatch(model_type, token_pattern, match_string))
                else:
                    if match_string in self._objs.get(model_type, {}):
                        id_matches.add(IdMatch(model_type, token_pattern, match_string))

        if not id_matches:
            if token_matches:
                return ("'{}', a {}.{}, contains the identifier(s) '{}', which aren't "
                        "the id(s) of an object".format(
                            self.expression, self.model_cls.__name__,
                            self.attr, "', '".join(token_matches)))
            return None

        if 1 < len(id_matches):
            # as lexers always do, pick the longest match
            id_matches_by_length = sorted(id_matches, key=lambda id_match: len(id_match.match_string))
            longest_length = len(id_matches_by_length[-1].match_string)
            longest_matches = set()
            while id_matches_by_length and len(id_matches_by_length[-1].match_string) == longest_length:
                longest_matches.add(id_matches_by_length.pop())
            id_matches = longest_matches

        if 1 < len(id_matches):
            # error: multiple, maximal length matches
            matches_error = ["'{}' as a {} id".format(id_val, model_type.__name__)
                             for model_type, _, id_val in sorted(id_matches, key=lambda id_match: id_match.model_type.__name__)]
            matches_error = ', '.join(matches_error)
            return "'{}', a {}.{}, contains multiple model object id matches: {}".format(
                self.expression, self.model_cls.__name__, self.attr, matches_error)

        else:
            # return a lexical match about a related id
            match = id_matches.pop()
            right_case_match_string = match.match_string
            if case_fold_match:
                right_case_match_string = match.match_string.casefold()
            return LexMatch(
                [ObjTablesToken(ObjTablesTokenCodes.obj_id, match.match_string, match.model_type, right_case_match_string,
                                self._objs[match.model_type][right_case_match_string])],
                len(match.token_pattern))

    def _get_func_call_id(self, idx, case_fold_match='unused'):
        """ Try to parse a Python math function call from `self._py_tokens` at `idx`

        Each `obj_tables` object `model_cls` that contains an expression which can use Python math
        functions must define the set of allowed functions in `Meta.expression_valid_functions` of the
        model_cls Expression Model.

        Args:
            idx (:obj:`int`): current index into `self._py_tokens`
            case_fold_match (:obj:`str`, optional): ignored keyword; makes `ParsedExpression.tokenize()` simpler

        Returns:
            :obj:`object`: If tokens do not match, return `None`. If tokens match,
                but their values are wrong, return an error `str`.
                If a function call is found, return a `LexMatch` describing it.
        """
        func_match = self._match_tokens(self.FUNC_PATTERN, idx)
        if func_match:
            func_name = self._py_tokens[idx].string
            # FUNC_PATTERN is "identifier ("
            # the closing paren ")" will simply be encoded as a ObjTablesToken with code == op

            # are Python math functions defined?
            if not hasattr(self.model_cls.Meta, 'expression_valid_functions'):
                return ("'{}', a {}.{}, contains the func name '{}', but {}.Meta doesn't "
                        "define 'expression_valid_functions'".format(self.expression,
                                                                     self.model_cls.__name__,
                                                                     self.attr, func_name,
                                                                     self.model_cls.__name__))

            function_ids = set([f.__name__ for f in self.model_cls.Meta.expression_valid_functions])

            # is the function allowed?
            if func_name not in function_ids:
                return ("'{}', a {}.{}, contains the func name '{}', but it isn't in "
                        "{}.Meta.expression_valid_functions: {}".format(self.expression,
                                                                        self.model_cls.__name__,
                                                                        self.attr, func_name,
                                                                        self.model_cls.__name__,
                                                                        ', '.join(function_ids)))

            # return a lexical match about a math function
            return LexMatch(
                [ObjTablesToken(ObjTablesTokenCodes.math_func_id, func_name), ObjTablesToken(ObjTablesTokenCodes.op, '(')],
                len(self.FUNC_PATTERN))

        # no match
        return None

    def tokenize(self, case_fold_match=False):
        """ Tokenize a Python expression in `self.expression`

        Args:
            case_fold_match (:obj:`bool`, optional): if set, casefold identifiers before matching;
                identifier keys in `self._objs` must already be casefold'ed; default = False

        Returns:

            * :obj:`list`: of :obj:`ObjTablesToken`\ s
            * :obj:`dict`: dict of Model instances used by this list, grouped by Model type
            * :obj:`list` of :obj:`str`: list of errors

        Raises:
            :obj:`ParsedExpressionError`: if `model_cls` does not have a `Meta` attribute
        """
        self.__reset_tokenization()

        if not self.expression:
            self.errors.append('Expression cannot be empty')
            return (None, None, self.errors)

        # detect and report bad tokens
        bad_tokens = set()
        for tok in self._py_tokens:
            if tok.exact_type not in self.LEGAL_TOKENS:
                if tok.string and tok.string != ' ':
                    bad_tokens.add(tok.string)
                else:
                    bad_tokens.add(token.tok_name[tok.type])
        if bad_tokens:
            self.errors.append("'{}', a {}.{}, contains bad token(s): '{}'".format(
                self.expression, self.model_cls.__name__,
                self.attr, "', '".join(bad_tokens)))
            return (None, None, self.errors)

        idx = 0
        while idx < len(self._py_tokens):

            # categorize token codes
            obj_tables_token_code = ObjTablesTokenCodes.other
            if self._py_tokens[idx].type == token.OP:
                obj_tables_token_code = ObjTablesTokenCodes.op
            elif self._py_tokens[idx].type == token.NUMBER:
                obj_tables_token_code = ObjTablesTokenCodes.number

            # a token that isn't an identifier needs no processing
            if self._py_tokens[idx].type != token.NAME:
                # record non-identifier token
                self._obj_tables_tokens.append(ObjTablesToken(obj_tables_token_code, self._py_tokens[idx].string))
                idx += 1
                continue

            matches = []
            tmp_errors = []
            for get_obj_tables_lex_el in [self._get_related_obj_id, self._get_disambiguated_id, self._get_func_call_id]:
                result = get_obj_tables_lex_el(idx, case_fold_match=case_fold_match)
                if result is not None:
                    if isinstance(result, str):
                        tmp_errors.append(result)
                    elif isinstance(result, LexMatch):
                        matches.append(result)
                    else:   # pragma no cover
                        raise ParsedExpressionError("Result is neither str nor LexMatch '{}'".format(result))

            # should find either matches or errors
            if not (matches or tmp_errors):
                raise ParsedExpressionError("No matches or errors found in '{}'".format(self.expression))
            # if only errors are found, break to return them
            if tmp_errors and not matches:
                self.errors = tmp_errors
                break

            # matches is a list of LexMatch, if it contains one longest match, use that, else report error
            # sort matches by Python token pattern length
            matches_by_length = sorted(matches, key=lambda lex_match: lex_match.num_py_tokens)
            longest_length = matches_by_length[-1].num_py_tokens
            longest_matches = []
            while matches_by_length and matches_by_length[-1].num_py_tokens == longest_length:
                longest_matches.append(matches_by_length.pop())
            if len(longest_matches) > 1:
                raise ParsedExpressionError("Multiple longest matches: '{}'".format(longest_matches))

            # good match
            # advance idx to the next token
            # record match data in self._obj_tables_tokens and self.related_objects
            match = longest_matches.pop()
            idx += match.num_py_tokens
            obj_tables_tokens = match.obj_tables_tokens
            self._obj_tables_tokens.extend(obj_tables_tokens)
            for obj_tables_token in obj_tables_tokens:
                if obj_tables_token.code == ObjTablesTokenCodes.obj_id:
                    self.related_objects[obj_tables_token.model_type][obj_tables_token.model_id] = obj_tables_token.model

        # detect ambiguous tokens
        valid_function_names = [func.__name__ for func in self.valid_functions]
        for obj_tables_token in self._obj_tables_tokens:
            if obj_tables_token.code in [ObjTablesTokenCodes.obj_id, ObjTablesTokenCodes.math_func_id]:
                matching_items = []

                for model_type in self.term_models:
                    if obj_tables_token.token_string in self._objs.get(model_type, {}):
                        matching_items.append(model_type.__name__)

                if obj_tables_token.token_string in valid_function_names:
                    matching_items.append('function')

                if len(matching_items) > 1:
                    self.errors.append('ObjTablesToken `{}` is ambiguous. ObjTablesToken matches a {} and a {}.'.format(
                        obj_tables_token.token_string, ', a '.join(matching_items[0:-1]), matching_items[-1]))

        if self.errors:
            return (None, None, self.errors)
        try:
            self._compiled_expression, self._compiled_namespace = self._compile()
        except SyntaxError as error:
            return (None, None, ['SyntaxError: ' + str(error)])

        self._compiled_expression_with_units, self._compiled_namespace_with_units = self._compile(with_units=True)
        return (self._obj_tables_tokens, self.related_objects, None)

    def test_eval(self, values=1., with_units=False):
        """ Test evaluate this :obj:`ParsedExpression` with the value of all models given by `values`

        This is used to validate this :obj:`ParsedExpression`, as well as for testing.

        Args:
            values (:obj:`float` or :obj:`dict`, optional): value(s) of models used by the test
                evaluation; if a scalar, then that value is used for all models; if a `dict` then
                it maps model types to their values, or it maps model types to dictionaries that map
                model ids to the values of individual models used in the test
            with_units (:obj:`bool`, optional): if :obj:`True`, evaluate units

        Returns:
            :obj:`float`, :obj:`int`, or :obj:`bool`: the value of the expression

        Raises:
            :obj:`ParsedExpressionError`: if the expression evaluation fails
        """
        def constant_factory(value):
            return lambda: value

        if isinstance(values, (int, float, bool)):
            obj_values = {}
            for model_type in self.related_objects.keys():
                obj_values[model_type] = collections.defaultdict(constant_factory(values))
        else:
            obj_values = {}
            for model_type, model_values in values.items():
                if isinstance(model_values, (int, float, bool)):
                    obj_values[model_type] = collections.defaultdict(constant_factory(model_values))
                else:
                    obj_values[model_type] = model_values

        return self.eval(obj_values, with_units=with_units)

    def eval(self, values, with_units=False):
        """ Evaluate the expression

        Approach:

            1. Ensure that the expression is compiled
            2. Prepare namespace with model values
            3. `eval` the Python expression

        Args:
            values (:obj:`dict`): dictionary that maps model types to dictionaries that
                map model ids to values
            with_units (:obj:`bool`, optional): if :obj:`True`, include units

        Returns:
            :obj:`float`, :obj:`int`, or :obj:`bool`: the value of the expression

        Raises:
            :obj:`ParsedExpressionError`: if the expression has not been compiled or the evaluation fails
        """
        if with_units:
            expression = self._compiled_expression_with_units
            namespace = self._compiled_namespace_with_units
        else:
            expression = self._compiled_expression
            namespace = self._compiled_namespace

        if not expression:
            raise ParsedExpressionError("Cannot evaluate '{}', as it not been successfully compiled".format(
                self.expression))

        # prepare name space
        for model_type, model_id_values in values.items():
            namespace[model_type.__name__] = model_id_values

        for model_type, model_ids in self.related_objects.items():
            if hasattr(model_type.Meta, 'expression_term_model') and model_type.Meta.expression_term_model:
                namespace[model_type.__name__] = {}
                for id, model in model_ids.items():
                    namespace[model_type.__name__][id] = model.expression._parsed_expression.eval(values)
            elif hasattr(model_type.Meta, 'expression_term_value') and model_type.Meta.expression_term_value:
                namespace[model_type.__name__] = {}
                for id, model in model_ids.items():
                    namespace[model_type.__name__][id] = getattr(model, model_type.Meta.expression_term_value)

        if with_units:
            for model_type, model_ids in self.related_objects.items():
                for id, model in model_ids.items():
                    if isinstance(namespace[model_type.__name__][id], bool):
                        namespace[model_type.__name__][id] = float(namespace[model_type.__name__][id])
                    units = getattr(model, model.Meta.expression_term_units)
                    if units is None:
                        raise ParsedExpressionError('Units must be defined')
                    if not isinstance(units, self.unit_registry.Unit):
                        raise ParsedExpressionError('Unsupported units "{}"'.format(units))
                    namespace[model_type.__name__][id] *= self.unit_registry.parse_expression(str(units))

        # prepare error message
        error_suffix = " cannot eval expression '{}' in {}; ".format(self.expression,
                                                                     self.model_cls.__name__)

        # evaluate compiled expression
        try:
            return eval(expression, {}, namespace)
        except SyntaxError as error:
            raise ParsedExpressionError("SyntaxError:" + error_suffix + str(error))
        except NameError as error:
            raise ParsedExpressionError("NameError:" + error_suffix + str(error))
        except Exception as error:
            raise ParsedExpressionError("Exception:" + error_suffix + str(error))

    def _compile(self, with_units=False):
        """ Compile expression for evaluation by `eval` method

        Args:
            with_units (:obj:`bool`, optional): if :obj:`True`, include units

        Returns:
            :obj:`str`: compiled expression for `eval`
            :obj:`dict`: compiled namespace
        """

        str_expression = self.get_str(self._obj_tables_token_to_str, with_units=with_units)
        compiled_expression = compile(str_expression, '<ParsedExpression>', 'eval')

        compiled_namespace = {func.__name__: func for func in self.valid_functions}
        if with_units and self.unit_registry:
            compiled_namespace['__dimensionless__'] = self.unit_registry.parse_expression('dimensionless')

        return compiled_expression, compiled_namespace

    def _obj_tables_token_to_str(self, token):
        """ Get a string representation of a token that represents an instance of :obj:`Model`

        Args:
            token (:obj:`ObjTablesToken`): token that represents an instance of :obj:`Model`

        Returns:
            :obj:`str`: string representation of a token that represents an instance of :obj:`Model`.
        """
        return '{}["{}"]'.format(token.model_type.__name__, token.model.get_primary_attribute())

    def get_str(self, obj_tables_token_to_str, with_units=False, number_units=' * __dimensionless__'):
        """ Generate string representation of expression, e.g. for evaluation by `eval`

        Args:
            obj_tables_token_to_str (:obj:`callable`): method to get string representation of a token
                that represents an instance of :obj:`Model`.
            with_units (:obj:`bool`, optional): if :obj:`True`, include units
            number_units (:obj:`str`, optional): default units for numbers

        Returns:
            :obj:`str`: string representation of expression

        Raises:
            :obj:`ParsedExpressionError`: if the expression is invalid
        """
        if not self._obj_tables_tokens:
            raise ParsedExpressionError("Cannot evaluate '{}', as it not been successfully tokenized".format(
                self.expression))

        tokens = []
        idx = 0
        while idx < len(self._obj_tables_tokens):
            obj_tables_token = self._obj_tables_tokens[idx]
            if obj_tables_token.code == ObjTablesTokenCodes.obj_id:
                val = obj_tables_token_to_str(obj_tables_token)
                tokens.append(val)
            elif obj_tables_token.code == ObjTablesTokenCodes.number:
                if with_units:
                    tokens.append(obj_tables_token.token_string + number_units)
                else:
                    tokens.append(obj_tables_token.token_string)
            else:
                tokens.append(obj_tables_token.token_string)
            idx += 1

        return ' '.join(tokens)

    def __str__(self):
        rv = []
        rv.append("model_cls: {}".format(self.model_cls.__name__))
        rv.append("expression: '{}'".format(self.expression))
        rv.append("attr: {}".format(self.attr))
        rv.append("py_tokens: {}".format("'" + "', '".join([t.string for t in self._py_tokens]) + "'"))
        rv.append("related_objects: {}".format(self.related_objects))
        rv.append("errors: {}".format(self.errors))
        rv.append("obj_tables_tokens: {}".format(self._obj_tables_tokens))
        return '\n'.join(rv)


class ParsedExpressionValidator(object):
    """ Verify whether a sequence of `ObjTablesToken` tokens

    A `ParsedExpressionValidator` consists of two parts:

    * An optional method `_validate_tokens` that examines the content of individual tokens
      and returns `(True, True)` if they are all valid, or (`False`, error) otherwise. It can be
      overridden by subclasses.
    * A `DFSMAcceptor` that determines whether the tokens describe a particular pattern.

    `validate()` combines these parts.

    Attributes:
        dfsm_acceptor (:obj:`DFSMAcceptor`): the DFSM acceptor
        empty_is_valid (:obj:`bool`): if set, then an empty sequence of tokens is valid
    """

    def __init__(self, start_state, accepting_state, transitions, empty_is_valid=False):
        """
        Args:
            start_state (:obj:`object`): a DFSM's start state
            accepting_state (:obj:`object`): a DFSM must be in this state to accept a message sequence
            transitions (:obj:`iterator` of `tuple`): transitions, an iterator of
                (state, message, next state) tuples
            empty_is_valid (:obj:`bool`, optional): if set, then an empty sequence of tokens is valid
        """
        self.dfsm_acceptor = DFSMAcceptor(start_state, accepting_state, transitions)
        self.empty_is_valid = empty_is_valid

    def _validate_tokens(self, tokens):
        """ Check whether the content of a sequence of :obj:`ObjTablesToken`\ s is valid

        Args:
            tokens (:obj:`iterator` of `ObjTablesToken`): sequence of `ObjTablesToken`s

        Returns:
            :obj:`tuple`: (`False`, error) if `tokens` is invalid, or (`True`, `True`) if it is valid
        """
        return (True, True)

    def _make_dfsa_messages(self, obj_table_tokens):
        """ Convert a sequence of :obj:`ObjTablesToken`\ s into a list of messages for transitions

        Args:
            obj_table_tokens (:obj:`iterator` of `ObjTablesToken`): sequence of `ObjTablesToken`s

        Returns:
            :obj:`object`: `list` of `tuple` of pairs (token code, `None`)
        """
        messages = []
        for obj_table_token in obj_table_tokens:
            messages.append((obj_table_token.code, None))
        return messages

    def validate(self, expression):
        """ Indicate whether the tokens in `expression` are valid

        Args:
            expression (:obj:`ParsedExpression`): parsed expression

        Returns:
            :obj:`tuple`: (`False`, error) if tokens in `expression` ares valid,
            or (`True`, `None`) if they are
        """
        tokens = expression._obj_tables_tokens
        if self.empty_is_valid and not tokens:
            return (True, None)
        valid, error = self._validate_tokens(tokens)
        if not valid:
            return (False, error)
        dfsa_messages = self._make_dfsa_messages(tokens)
        if DFSMAcceptor.ACCEPT == self.dfsm_acceptor.run(dfsa_messages):
            return (True, None)
        else:
            return (False, "Not a valid expression")


class LinearParsedExpressionValidator(ParsedExpressionValidator):
    """ Verify whether a sequence of tokens (`ObjTablesToken`\ s) describes a linear function of identifiers

    In particular, a valid linear expression must have the structure:
        * `(identifier | number '*' identifier) (('+' | '-') (identifier | number '*' identifier))*`
    """

    # Transitions in valid linear expression
    TRANSITIONS = [   # (current state, message, next state)
        ('need number or id', (ObjTablesTokenCodes.number, None), 'need * id'),
        ('need * id', (ObjTablesTokenCodes.op, '*'), 'need id'),
        ('need id', (ObjTablesTokenCodes.obj_id, None), 'need + | - | end'),
        ('need number or id', (ObjTablesTokenCodes.obj_id, None), 'need + | - | end'),
        ('need + | - | end', (ObjTablesTokenCodes.op, '+'), 'need number or id'),
        ('need + | - | end', (ObjTablesTokenCodes.op, '-'), 'need number or id'),
        ('need + | - | end', (None, None), 'end'),
    ]

    def __init__(self):
        super().__init__(start_state='need number or id', accepting_state='end',
                         transitions=self.TRANSITIONS, empty_is_valid=True)

    def _validate_tokens(self, obj_table_tokens):
        """ Check whether the content of a sequence of :obj:`ObjTablesToken`\ s is valid

        In particular, all numbers in `tokens` must be floats, and all token codes must not
        be `math_func_id` or `other`.

        Args:
            obj_table_tokens (:obj:`iterator` of `ObjTablesToken`): sequence of `ObjTablesToken`s

        Returns:
            :obj:`tuple`: (`False`, error) if `tokens` cannot be a linear expression, or
                (`True`, `True`) if it can
        """
        for obj_table_token in obj_table_tokens:
            if obj_table_token.code in set([ObjTablesTokenCodes.math_func_id, ObjTablesTokenCodes.other]):
                return (False, "messages do not use token codes `math_func_id` or `other`")
            if obj_table_token.code == ObjTablesTokenCodes.number:
                try:
                    float(obj_table_token.token_string)
                except ValueError as e:
                    return (False, str(e))

        return (True, True)

    def _make_dfsa_messages(self, obj_table_tokens):
        """ Convert a sequence of :obj:`ObjTablesToken`\ s into a list of messages for transitions in
        :obj:`LinearParsedExpressionValidator.TRANSITIONS`

        Args:
            obj_table_tokens (:obj:`iterator` of `ObjTablesToken`): sequence of `ObjTablesToken`s

        Returns:
            :obj:`object`: :obj:`None` if `tokens` cannot be converted into a sequence of messages
                to validate a linear expression, or a :obj:`list` of :obj:`tuple` of pairs (token code, message modifier)
        """
        messages = []
        for obj_table_token in obj_table_tokens:
            message_tok_code = obj_table_token.code
            if obj_table_token.code == ObjTablesTokenCodes.obj_id:
                message_modifier = None
            elif obj_table_token.code == ObjTablesTokenCodes.number:
                message_modifier = None
            elif obj_table_token.code == ObjTablesTokenCodes.op:
                message_modifier = obj_table_token.token_string
            else:
                return None
            messages.append((message_tok_code, message_modifier))
        messages.append((None, None))
        return messages
