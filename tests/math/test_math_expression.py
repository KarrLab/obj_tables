"""
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Author: Jonathan Karr  <karr@mssm.edu>
:Date: 2018-12-19
:Copyright: 2016-2019, Karr Lab
:License: MIT
"""

import astor
import gc
import mock
import random
import re
import token
import unittest

from obj_tables.core import (Model, SlugAttribute, FloatAttribute, StringAttribute,
                             ManyToOneAttribute, ManyToManyAttribute,
                             InvalidObject, InvalidAttribute)
from obj_tables.math.expression import (OneToOneExpressionAttribute, ManyToOneExpressionAttribute,
                                        ExpressionStaticTermMeta, ExpressionDynamicTermMeta,
                                        ExpressionExpressionTermMeta,
                                        ObjTablesTokenCodes, ObjTablesToken, LexMatch,
                                        Expression, ParsedExpression,
                                        LinearParsedExpressionValidator,
                                        ParsedExpressionError)
from obj_tables.sci.units import UnitAttribute
from wc_utils.util.units import unit_registry


class BaseModel(Model):
    id = SlugAttribute()


class Parameter(Model):
    id = SlugAttribute()
    model = ManyToOneAttribute(BaseModel, related_name='parameters')
    value = FloatAttribute()
    units = UnitAttribute(unit_registry)

    class Meta(Model.Meta, ExpressionStaticTermMeta):
        expression_term_value = 'value'
        expression_term_units = 'units'


class Species(Model):
    id = StringAttribute(primary=True, unique=True)
    model = ManyToOneAttribute(BaseModel, related_name='species')
    units = UnitAttribute(unit_registry)

    class Meta(Model.Meta, ExpressionDynamicTermMeta):
        expression_term_token_pattern = (token.NAME, token.LSQB, token.NAME, token.RSQB)
        expression_term_units = 'units'


class SubFunctionExpression(Model, Expression):
    expression = StringAttribute()
    parameters = ManyToManyAttribute(Parameter, related_name='sub_function_expressions')
    sub_functions = ManyToManyAttribute('SubFunction', related_name='sub_function_expressions')

    class Meta(Model.Meta, Expression.Meta):
        expression_term_models = ('SubFunction', 'Parameter',)
        expression_unit_registry = unit_registry

    def serialize(self): return Expression.serialize(self)

    @classmethod
    def deserialize(cls, value, objects): return Expression.deserialize(cls, value, objects)

    def validate(self): return Expression.validate(self, self.parent_sub_function)

    def merge_attrs(self, other, other_objs_in_self, self_objs_in_other):
        super(SubFunctionExpression, self).merge_attrs(other, other_objs_in_self, self_objs_in_other)
        Expression.merge_attrs(self, other, other_objs_in_self, self_objs_in_other)


class SubFunction(Model):
    id = SlugAttribute()
    model = ManyToOneAttribute(BaseModel, related_name='sub_functions')
    expression = OneToOneExpressionAttribute(SubFunctionExpression, related_name='parent_sub_function')
    units = UnitAttribute(unit_registry)

    class Meta(Model.Meta, ExpressionExpressionTermMeta):
        expression_term_model = SubFunctionExpression


class BooleanSubFunctionExpression(Model, Expression):
    expression = StringAttribute()
    parameters = ManyToManyAttribute(Parameter, related_name='boolean_sub_function_expressions')

    class Meta(Model.Meta, Expression.Meta):
        expression_term_models = ('Parameter',)
        expression_unit_registry = unit_registry

    def serialize(self): return Expression.serialize(self)

    @classmethod
    def deserialize(cls, value, objects): return Expression.deserialize(cls, value, objects)

    def validate(self): return Expression.validate(self, self.boolean_sub_function)

    def merge_attrs(self, other, other_objs_in_self, self_objs_in_other):
        super(BooleanSubFunctionExpression, self).merge_attrs(other, other_objs_in_self, self_objs_in_other)
        Expression.merge_attrs(self, other, other_objs_in_self, self_objs_in_other)


class BooleanSubFunction(Model):
    id = SlugAttribute()
    model = ManyToOneAttribute(BaseModel, related_name='boolean_sub_functions')
    expression = OneToOneExpressionAttribute(BooleanSubFunctionExpression, related_name='boolean_sub_function')
    units = UnitAttribute(unit_registry, choices=(unit_registry.parse_units('dimensionless'),),
                          default=unit_registry.parse_units('dimensionless'))

    class Meta(Model.Meta, ExpressionExpressionTermMeta):
        expression_term_model = BooleanSubFunctionExpression


class LinearSubFunctionExpression(Model, Expression):
    expression = StringAttribute()
    parameters = ManyToManyAttribute(Parameter, related_name='linear_sub_function_expressions')

    class Meta(Model.Meta, Expression.Meta):
        expression_term_models = ('Parameter',)
        expression_is_linear = True
        expression_unit_registry = unit_registry

    def serialize(self): return Expression.serialize(self)

    @classmethod
    def deserialize(cls, value, objects): return Expression.deserialize(cls, value, objects)

    def validate(self): return Expression.validate(self, self.linear_sub_function)

    def merge_attrs(self, other, other_objs_in_self, self_objs_in_other):
        super(LinearSubFunctionExpression, self).merge_attrs(other, other_objs_in_self, self_objs_in_other)
        Expression.merge_attrs(self, other, other_objs_in_self, self_objs_in_other)


class LinearSubFunction(Model):
    id = SlugAttribute()
    model = ManyToOneAttribute(BaseModel, related_name='linear_sub_functions')
    expression = ManyToOneExpressionAttribute(LinearSubFunctionExpression, related_name='linear_sub_function')
    units = UnitAttribute(unit_registry)

    class Meta(Model.Meta, ExpressionExpressionTermMeta):
        expression_term_model = LinearSubFunctionExpression


class FunctionExpression(Model, Expression):
    expression = StringAttribute()
    sub_functions = ManyToManyAttribute(SubFunction, related_name='function_expressions')
    linear_sub_functions = ManyToManyAttribute(LinearSubFunction, related_name='function_expressions')
    parameters = ManyToManyAttribute(Parameter, related_name='function_expressions')
    species = ManyToManyAttribute(Species, related_name='function_expressions')

    class Meta(Model.Meta, Expression.Meta):
        expression_term_models = ('SubFunction', 'LinearSubFunction', 'Parameter', 'Species')
        expression_type = float
        expression_unit_registry = unit_registry

    def serialize(self): return Expression.serialize(self)

    @classmethod
    def deserialize(cls, value, objects): return Expression.deserialize(cls, value, objects)

    def validate(self): return Expression.validate(self, self.function)

    def merge_attrs(self, other, other_objs_in_self, self_objs_in_other):
        super(FunctionExpression, self).merge_attrs(other, other_objs_in_self, self_objs_in_other)
        Expression.merge_attrs(self, other, other_objs_in_self, self_objs_in_other)


class Function(Model):
    id = SlugAttribute()
    model = ManyToOneAttribute(BaseModel, related_name='functions')
    expression = OneToOneExpressionAttribute(FunctionExpression, related_name='function')
    units = UnitAttribute(unit_registry)

    class Meta(Model.Meta, ExpressionExpressionTermMeta):
        expression_term_model = FunctionExpression


class ExpressionAttributesTestCase(unittest.TestCase):
    def test_one_to_one_serialize(self):
        expr = 'p_1 + p_2'
        p_1 = Parameter(id='p_1', value=2., units=unit_registry.parse_units('dimensionless'))
        p_2 = Parameter(id='p_2', value=3., units=unit_registry.parse_units('dimensionless'))
        expression, error = FunctionExpression.deserialize(expr, {
            Parameter: {p_1.id: p_1, p_2.id: p_2},
        })
        assert error is None, str(error)
        self.assertEqual(Function.expression.serialize(expression), expr)
        self.assertEqual(Function.expression.serialize(''), '')
        self.assertEqual(Function.expression.serialize(None), '')

    def test_one_to_one_deserialize(self):
        expr = 'p_1 + p_2'
        p_1 = Parameter(id='p_1', value=2., units=unit_registry.parse_units('dimensionless'))
        p_2 = Parameter(id='p_2', value=3., units=unit_registry.parse_units('dimensionless'))

        expression, error = Function.expression.deserialize(expr, {
            Parameter: {p_1.id: p_1, p_2.id: p_2},
        })
        assert error is None, str(error)
        self.assertEqual(Function.expression.serialize(expression), expr)

        self.assertEqual(Function.expression.deserialize('', {}), (None, None))

    def test_many_to_one_serialize(self):
        expr = 'p_1 + p_2'
        p_1 = Parameter(id='p_1', value=2., units=unit_registry.parse_units('dimensionless'))
        p_2 = Parameter(id='p_2', value=3., units=unit_registry.parse_units('dimensionless'))
        expression, error = LinearSubFunctionExpression.deserialize(expr, {
            Parameter: {p_1.id: p_1, p_2.id: p_2},
        })
        assert error is None, str(error)
        self.assertEqual(LinearSubFunction.expression.serialize(expression), expr)
        self.assertEqual(LinearSubFunction.expression.serialize(''), '')
        self.assertEqual(LinearSubFunction.expression.serialize(None), '')

    def test_many_to_one_deserialize(self):
        expr = 'p_1 + p_2'
        p_1 = Parameter(id='p_1', value=2., units=unit_registry.parse_units('dimensionless'))
        p_2 = Parameter(id='p_2', value=3., units=unit_registry.parse_units('dimensionless'))

        expression, error = LinearSubFunction.expression.deserialize(expr, {
            Parameter: {p_1.id: p_1, p_2.id: p_2},
        })
        assert error is None, str(error)
        self.assertEqual(LinearSubFunction.expression.serialize(expression), expr)

        self.assertEqual(LinearSubFunction.expression.deserialize('', {}), (None, None))


class ExpressionTestCase(unittest.TestCase):
    def test_deserialize_repeated(self):
        expr_1 = FunctionExpression()
        objects = {FunctionExpression: {'1': expr_1}}

        expr_2, error = FunctionExpression.deserialize('1', objects)
        self.assertEqual(error, None)

        self.assertEqual(expr_2, expr_1)

    def test_deserialize_is_linear(self):
        objects = {
            Parameter: {
                'p_1': Parameter(id='p_1'),
                'p_2': Parameter(id='p_2'),
                'p_3': Parameter(id='p_3'),
            },
        }

        expr, error = FunctionExpression.deserialize('p_1 + p_2 + p_3', objects)
        self.assertTrue(expr._parsed_expression.is_linear)

        expr, error = FunctionExpression.deserialize('p_1 + p_2 - p_3', objects)
        self.assertTrue(expr._parsed_expression.is_linear)

        expr, error = FunctionExpression.deserialize('p_1 + p_2 + 2 * p_3', objects)
        self.assertTrue(expr._parsed_expression.is_linear)

        expr, error = FunctionExpression.deserialize('p_1 * p_2 + p_3', objects)
        self.assertFalse(expr._parsed_expression.is_linear)

    def test_deserialize_error(self):
        rv = FunctionExpression.deserialize('1 * ', {})
        self.assertEqual(rv[0], None)
        self.assertRegex(str(rv[1]), 'SyntaxError:')

        rv = Expression.deserialize(FunctionExpression, '1 * ', {})
        self.assertEqual(rv[0], None)
        self.assertRegex(str(rv[1]), 'SyntaxError:')

        rv = Expression.deserialize(Function, '1 * ', {})
        self.assertEqual(rv[0], None)
        self.assertRegex(str(rv[1]), "doesn't have a 'Meta.expression_term_models' attribute")

    def test_set_lin_coeffs(self):
        # test linear coeffs of expressions like reactions split in dFBA objective expressions in wc_lang
        objects = {
            Parameter: {
                'r_for': Parameter(id='r_for'),
                'r_back': Parameter(id='r_back'),
            },
        }

        str_expr_and_expt_lin_coeffs = [('(r_for - r_back)', dict(r_for=1., r_back=-1.)),
                                        ('2 * (r_for - r_back)', dict(r_for=2., r_back=-2.)),
                                        ('-2 * (r_for - r_back)', dict(r_for=-2., r_back=2.)),
                                        ('2 * (r_for - r_back) + -(r_for - r_back)', dict(r_for=1., r_back=-1.)),
        ]
        for str_expr, expt_lin_coeffs in str_expr_and_expt_lin_coeffs:
            expr, error = FunctionExpression.deserialize(str_expr, objects)
            self.assertEqual(expr.validate(), None)
            parsed_expr = expr._parsed_expression
            self.assertTrue(parsed_expr.is_linear)
            self.assertEqual(set([p.id for p in parsed_expr.lin_coeffs[Parameter]]),
                             set(expt_lin_coeffs))
            for param, coeff in parsed_expr.lin_coeffs[Parameter].items():
                self.assertEqual(expt_lin_coeffs[param.id], coeff)

    def test_validate(self):
        objects = {
            Parameter: {
                'p_1': Parameter(id='p_1'),
                'p_2': Parameter(id='p_2'),
                'p_3': Parameter(id='p_3'),
            },
        }

        expr, error = FunctionExpression.deserialize('p_1 + p_2+ p_3', objects)
        self.assertEqual(expr.validate(), None)

        expr, error = FunctionExpression.deserialize('p_1 + p_2 + p_3', objects)
        expr.expression = 'p_1 * p_4'
        self.assertNotEqual(expr.validate(), None)

        expr, error = FunctionExpression.deserialize('p_1 + p_2 + p_3', objects)
        expr.expression = 'p_1 + p_2'
        self.assertNotEqual(expr.validate(), None)

        expr, error = FunctionExpression.deserialize('p_1 + p_2 * p_3', objects)
        self.assertEqual(expr.validate(), None)
        expr, error = LinearSubFunctionExpression.deserialize('p_1 + p_2 * p_3', objects)
        self.assertNotEqual(expr.validate(), None)

        expr, error = FunctionExpression.deserialize('p_1 > p_2', objects)
        self.assertNotEqual(expr.validate(), None)
        expr, error = SubFunctionExpression.deserialize('p_1 > p_2', objects)
        self.assertEqual(expr.validate(), None)

        expr, error = FunctionExpression.deserialize('p_1 + p_2 + p_3', objects)
        expr.expression = '1['
        rv = Expression.validate(expr, None)
        self.assertRegex(str(rv), 'Python syntax error')

        expr, error = FunctionExpression.deserialize('p_1 + p_2 + p_3', objects)
        expr.expression = 'p_1 + p_2 + p_3 + 1 / 0'
        rv = Expression.validate(expr, None)
        self.assertRegex(str(rv), 'cannot eval expression')

    def test_make_expression_obj(self):
        objects = {
            Parameter: {
                'p_1': Parameter(id='p_1'),
                'p_2': Parameter(id='p_2'),
                'p_3': Parameter(id='p_3'),
            },
        }
        rv = Expression.make_expression_obj(Function, 'p_1 + p_2 + p_3', objects)
        self.assertIsInstance(rv[0], FunctionExpression)
        self.assertEqual(rv[1], None)

    def test_make_obj(self):
        objects = {
            Parameter: {
                'p_1': Parameter(id='p_1'),
                'p_2': Parameter(id='p_2'),
                'p_3': Parameter(id='p_3'),
            },
        }

        func_1 = Expression.make_obj(BaseModel(), Function, 'func_1', 'p_1 + p_2 + p_3', objects)
        self.assertIsInstance(func_1, Function)
        self.assertEqual(func_1.id, 'func_1')
        self.assertEqual(func_1.expression.expression, 'p_1 + p_2 + p_3')

        self.assertIsInstance(Expression.make_obj(BaseModel(), Function, 'func_1', 'p_1 + p_2 + ', objects), InvalidAttribute)

        self.assertIsInstance(Expression.make_obj(BaseModel(), LinearSubFunction, 'func_1',
                                                  'p_1 * p_2 + p_3', objects), InvalidObject)

    def test_merge(self):
        model_a = BaseModel(id='model')
        model_b = BaseModel(id='model')
        model_ab = BaseModel(id='model')
        objects_a = {
            Parameter: {
                'p_1': Parameter(model=model_a, id='p_1'),
                'p_2': Parameter(model=model_a, id='p_2'),
                'p_3': Parameter(model=model_a, id='p_3'),
            },
        }
        objects_b = {
            Parameter: {
                'p_1': Parameter(model=model_b, id='p_1'),
                'p_2': Parameter(model=model_b, id='p_2'),
                'p_3': Parameter(model=model_b, id='p_3'),
            },
        }
        objects_ab = {
            Parameter: {
                'p_1': Parameter(model=model_ab, id='p_1'),
                'p_2': Parameter(model=model_ab, id='p_2'),
                'p_3': Parameter(model=model_ab, id='p_3'),
            },
        }

        func_1_a = Expression.make_obj(model_a, Function, 'func_1', 'p_1 + p_2', objects_a)
        func_2_b = Expression.make_obj(model_b, Function, 'func_2', 'p_1 + p_3', objects_b)
        func_1_ab = Expression.make_obj(model_ab, Function, 'func_1', 'p_1 + p_2', objects_ab)
        func_2_ab = Expression.make_obj(model_ab, Function, 'func_2', 'p_1 + p_3', objects_ab)

        merged_model = model_a.copy()
        merged_model.merge(model_b.copy())
        self.assertTrue(merged_model.is_equal(model_ab))

        merged_model = model_b.copy()
        merged_model.merge(model_a.copy())
        self.assertTrue(merged_model.is_equal(model_ab))


class ParsedExpressionTestCase(unittest.TestCase):

    @staticmethod
    def esc_re_center(re_list):
        return '.*' + '.*'.join([re.escape(an_re) for an_re in re_list]) + '.*'

    def test___init__(self):
        expr = '3 + 5 * 6'
        parsed_expr = ParsedExpression(SubFunctionExpression, 'attr', ' ' + expr + ' ', {})
        self.assertEqual(expr, parsed_expr.expression)

        # test integer and float expressions
        expr = 3
        parsed_expr = ParsedExpression(SubFunctionExpression, 'attr', expr, {})
        self.assertEqual(str(expr), parsed_expr.expression)
        expr = 0.5
        parsed_expr = ParsedExpression(SubFunctionExpression, 'attr', expr, {})
        self.assertEqual(str(expr), parsed_expr.expression)

        with self.assertRaisesRegex(ParsedExpressionError, 'is not a subclass of Model'):
            ParsedExpression(int, 'attr', expr, {})

        with self.assertRaisesRegex(ParsedExpressionError, "doesn't have a 'Meta.expression_term_models' attribute"):
            ParsedExpression(Model, 'attr', expr, {})

        with self.assertRaisesRegex(ParsedExpressionError, "creates a Python syntax error"):
            ParsedExpression(SubFunctionExpression, 'attr', '3(', {})

        with self.assertRaisesRegex(ParsedExpressionError,
                                    "Expression '.*' in .* must be string, float or integer"):
            ParsedExpression(SubFunctionExpression, 'attr', list(), {})

        class TestModelExpression(Model):
            class Meta(Model.Meta):
                expression_term_models = ('Function',)
                expression_unit_registry = unit_registry
        with self.assertRaisesRegex(ParsedExpressionError, 'must have a relationship to'):
            ParsedExpression(TestModelExpression, 'attr', expr, {})

    def test_parsed_expression(self):
        expr = '3 + 5 * 6'
        parsed_expr = ParsedExpression(FunctionExpression, 'attr', ' ' + expr + ' ', {})
        self.assertEqual(expr, parsed_expr.expression)
        n = 5
        parsed_expr = ParsedExpression(FunctionExpression, 'attr', ' + ' * n, {})
        self.assertEqual([token.PLUS] * n, [tok.exact_type for tok in parsed_expr._py_tokens])
        parsed_expr = ParsedExpression(FunctionExpression, 'attr', '', {})
        self.assertEqual(parsed_expr.valid_functions, set(FunctionExpression.Meta.expression_valid_functions))
        parsed_expr = ParsedExpression(FunctionExpression, 'attr', '', {Function: {}, Parameter: {}})
        self.assertEqual(parsed_expr.valid_functions, set(FunctionExpression.Meta.expression_valid_functions))
        expr = 'id1[id2'
        with self.assertRaisesRegex(
                ParsedExpressionError,
                "parsing '{}'.*creates a Python syntax error.*".format(re.escape(expr))):
            self.make_parsed_expr(expr)
        with self.assertRaisesRegex(
                ParsedExpressionError,
                "model_cls 'Species' doesn't have a 'Meta.expression_term_models' attribute"):
            ParsedExpression(Species, 'attr', '', {})

    def test_trailing_whitespace(self):
        # whitespace lengths = 0, 1, ...:
        expr = '1* 2  +   8 '
        wc_lang_expr = self.make_parsed_expr(expr)
        for idx in range(4):
            self.assertEqual(wc_lang_expr._get_trailing_whitespace(idx), idx)
        self.assertEqual(wc_lang_expr._get_trailing_whitespace(4), 0)
        self.assertEqual(self.make_parsed_expr('')._get_trailing_whitespace(0), 0)

    def test_recreate_whitespace(self):
        # whitespace lengths = 0, 1, ...:
        expr = 'param_id- Observable.obs_id  *   Function.fun_1()    +     1      -       1p'
        wc_lang_expr = self.make_parsed_expr(expr)
        expr_new = expr.replace('Observable', 'NewObservable').replace('Function', 'NoFun')
        expr_no_whitespace = expr_new.replace(' ', '')
        expr_w_same_whitespace = wc_lang_expr.recreate_whitespace(expr_no_whitespace)
        ws_len = 1
        for spaces in re.findall(' +', expr_w_same_whitespace):
            self.assertEqual(len(spaces), ws_len)
            ws_len += 1

        with self.assertRaisesRegex(ParsedExpressionError,
                                    "parsing '.*' creates a Python syntax error: '.*'"):
            wc_lang_expr.recreate_whitespace(expr_no_whitespace + ' x[y')
        with self.assertRaisesRegex(ParsedExpressionError,
                                    "can't recreate whitespace in '.*', as it has .* instead of .* tokens expected"):
            wc_lang_expr.recreate_whitespace(expr_no_whitespace + ' +1')

    def test_parsed_expression_ambiguous(self):
        func, error = FunctionExpression.deserialize('min(p_1, p_2)', {
            Parameter: {
                'min': Parameter(id='min', value=1.),
                'p_1': Parameter(id='p_1', value=2.),
                'p_2': Parameter(id='p_2', value=3.),
            }
        })
        self.assertEqual(func, None)
        self.assertRegex(str(error), 'is ambiguous. ObjTablesToken matches')

    def test__get_model_type(self):
        expr = '3 + 5 * 6'
        parsed_expr = ParsedExpression(SubFunctionExpression, 'attr', expr, {})
        self.assertEqual(parsed_expr._get_model_type('SubFunction'), SubFunction)
        self.assertEqual(parsed_expr._get_model_type('NoSuchType'), None)

    def make_parsed_expr(self, expr, obj_type=FunctionExpression, objects=None):
        objects = objects or {}
        return ParsedExpression(obj_type, 'expr_attr', expr, objects)

    def do_match_tokens_test(self, expr, pattern, expected, idx=0):
        parsed_expr = self.make_parsed_expr(expr)
        self.assertEqual(parsed_expr._match_tokens(pattern, idx), expected)

    def test_match_tokens(self):
        self.do_match_tokens_test('', [], False)
        single_name_pattern = (token.NAME, )
        self.do_match_tokens_test('', single_name_pattern, False)
        self.do_match_tokens_test('ID2', single_name_pattern, 'ID2')
        self.do_match_tokens_test('ID3 5', single_name_pattern, 'ID3')
        # fail to match tokens
        self.do_match_tokens_test('+ 5', single_name_pattern, False)
        # call _match_tokens with 0<idx
        self.do_match_tokens_test('7 ID3', single_name_pattern, 'ID3', idx=1)
        self.do_match_tokens_test('2+ 5', single_name_pattern, False, idx=1)

        pattern = (token.NAME, token.LSQB, token.NAME, token.RSQB)
        self.do_match_tokens_test('sp1[c1]+', pattern, 'sp1[c1]')
        self.do_match_tokens_test('sp1 +', pattern, False)
        # whitespace is not allowed between tokens in an ID
        self.do_match_tokens_test('sp1 [ c1 ] ', pattern, False)

    def do_disambiguated_id_error_test(self, expr, expected):
        parsed_expr = self.make_parsed_expr(expr)
        result = parsed_expr._get_disambiguated_id(0)
        self.assertTrue(isinstance(result, str))
        self.assertIn(expected.format(expr), result)

    def do_disambiguated_id_test(self, expr, disambig_type, id, pattern, case_fold_match=False, objects=None):
        parsed_expr = self.make_parsed_expr(expr, objects=objects)
        lex_match = parsed_expr._get_disambiguated_id(0, case_fold_match=case_fold_match)
        self.assertIsInstance(lex_match, LexMatch)
        self.assertEqual(lex_match.num_py_tokens, len(pattern))
        self.assertEqual(len(lex_match.obj_tables_tokens), 1)
        obj_tables_token = lex_match.obj_tables_tokens[0]
        self.assertEqual(obj_tables_token,
                         # note: obj_tables_token.model is cheating
                         ObjTablesToken(ObjTablesTokenCodes.obj_id, expr, disambig_type,
                                        id, obj_tables_token.model))

    def test_disambiguated_id(self):
        self.do_disambiguated_id_error_test(
            'Parameter.foo2',
            "contains '{}', but 'foo2' is not the id of a 'Parameter'")

        self.do_disambiguated_id_error_test(
            'NotFunction.foo',
            "contains '{}', but the disambiguation model type 'NotFunction' cannot be referenced by ")
        self.do_disambiguated_id_error_test(
            'NoSuchModel.fun_1',
            "contains '{}', but the disambiguation model type 'NoSuchModel' cannot be referenced by "
            "'FunctionExpression' expressions")
        self.do_disambiguated_id_error_test(
            'Parameter.fun_1',
            "contains '{}', but 'fun_1' is not the id of a 'Parameter'")

        objects = {
            SubFunction: {'test_id': SubFunction(id='test_id')}
        }
        self.do_disambiguated_id_test('SubFunction.test_id', SubFunction, 'test_id',
                                      ParsedExpression.MODEL_TYPE_DISAMBIG_PATTERN, objects=objects)
        self.do_disambiguated_id_test('SubFunction.TEST_ID', SubFunction, 'test_id',
                                      ParsedExpression.MODEL_TYPE_DISAMBIG_PATTERN, objects=objects, case_fold_match=True)

        # do not find a match
        parsed_expr = self.make_parsed_expr('3 * 2')
        self.assertEqual(parsed_expr._get_disambiguated_id(0), None)

    def do_related_object_id_error_test(self, expr, expected_error, objects):
        parsed_expr = self.make_parsed_expr(expr, objects=objects)
        result = parsed_expr._get_related_obj_id(0)
        self.assertIsInstance(result, str)
        self.assertRegex(result, self.esc_re_center(expected_error))

    def test_related_object_id_errors(self):
        objects = {}
        self.do_related_object_id_error_test(
            'x[c]',
            ["contains the identifier(s)", "which aren't the id(s) of an object"],
            objects)

    def test_related_object_id_mult_matches_error(self):
        objects = {
            SubFunction: {'test_id': SubFunction()},
            LinearSubFunction: {'test_id': LinearSubFunction()},
        }
        self.do_related_object_id_error_test(
            'test_id',
            ["multiple model object id matches: 'test_id' as a LinearSubFunction id, 'test_id' as a SubFunction id"],
            objects)

    def do_related_object_id_test(self, expr, expected_token_string, expected_related_type,
                                  expected_id, pattern, case_fold_match=False, objects=None):
        parsed_expr = self.make_parsed_expr(expr, objects=objects)
        lex_match = parsed_expr._get_related_obj_id(0, case_fold_match=case_fold_match)
        self.assertIsInstance(lex_match, LexMatch)
        self.assertEqual(lex_match.num_py_tokens, len(pattern))
        self.assertEqual(len(lex_match.obj_tables_tokens), 1)
        obj_tables_token = lex_match.obj_tables_tokens[0]

        self.assertEqual(obj_tables_token,
                         # note: obj_tables_token.model is cheating
                         ObjTablesToken(ObjTablesTokenCodes.obj_id, expected_token_string,
                                        expected_related_type,
                                        expected_id, obj_tables_token.model))

    def test_related_object_id_matches(self):
        objects = {
            Parameter: {'test_id': Parameter(id='test_id')},
            SubFunction: {'sub_func': SubFunction(id='sub_func')},
        }
        self.do_related_object_id_test('test_id + 3*x', 'test_id', Parameter, 'test_id',
                                       Parameter.Meta.expression_term_token_pattern, objects=objects)
        self.do_related_object_id_test('sub_func', 'sub_func', SubFunction, 'sub_func', (token.NAME, ), objects=objects)
        self.do_related_object_id_test('sub_Func', 'sub_Func', SubFunction, 'sub_func', (token.NAME, ),
                                       objects=objects, case_fold_match=True)
        self.do_related_object_id_test('SUB_FUNC', 'SUB_FUNC', SubFunction, 'sub_func', (token.NAME, ),
                                       objects=objects, case_fold_match=True)

        # no token matches
        parsed_expr = self.make_parsed_expr("3 * 4")
        self.assertEqual(parsed_expr._get_related_obj_id(0), None)

    def do_fun_call_error_test(self, expr, expected_error, obj_type=FunctionExpression):
        parsed_expr = self.make_parsed_expr(expr, obj_type=obj_type)
        result = parsed_expr._get_func_call_id(0)
        self.assertTrue(isinstance(result, str))
        self.assertRegex(result, self.esc_re_center(expected_error))

    def test_fun_call_id_errors(self):
        self.do_fun_call_error_test('foo(3)', ["contains the func name ",
                                               "but it isn't in {}.Meta.expression_valid_functions".format(
                                                   FunctionExpression.__name__)])

        class TestModelExpression(Model):
            functions = ManyToManyAttribute(Function, related_name='test_model_expressions')

            class Meta(Model.Meta):
                expression_term_models = ('Function',)
                expression_unit_registry = unit_registry
        self.do_fun_call_error_test('foo(3)', ["contains the func name ",
                                               "but {}.Meta doesn't define 'expression_valid_functions'".format(
                                                   TestModelExpression.__name__)],
                                    obj_type=TestModelExpression)

    def test_fun_call_id(self):
        parsed_expr = self.make_parsed_expr('log(3)')
        lex_match = parsed_expr._get_func_call_id(0)
        self.assertTrue(isinstance(lex_match, LexMatch))
        self.assertEqual(lex_match.num_py_tokens, len(parsed_expr.FUNC_PATTERN))
        self.assertEqual(len(lex_match.obj_tables_tokens), 2)
        self.assertEqual(lex_match.obj_tables_tokens[0], ObjTablesToken(ObjTablesTokenCodes.math_func_id, 'log'))
        self.assertEqual(lex_match.obj_tables_tokens[1], ObjTablesToken(ObjTablesTokenCodes.op, '('))

        # no token match
        parsed_expr = self.make_parsed_expr('no_fun + 3')
        self.assertEqual(parsed_expr._get_func_call_id(0), None)

    def test_bad_tokens(self):
        rv, _, errors = ParsedExpression(FunctionExpression, 'test', '+= *= @= : {}', {}).tokenize()
        self.assertEqual(rv, None)
        for bad_tok in ['+=', '*=', '@=', ':', '{', '}']:
            self.assertRegex(errors[0], r'.*contains bad token\(s\):.*' + re.escape(bad_tok) + '.*')
        # test bad tokens that don't have string values
        rv, _, errors = ParsedExpression(FunctionExpression, 'test', """
 3
 +1""", {}).tokenize()
        self.assertEqual(rv, None)
        self.assertRegex(errors[0], re.escape("contains bad token(s)"))

    def do_tokenize_id_test(self, expr, expected_wc_tokens, expected_related_objs,
                            model_type=FunctionExpression,
                            test_objects=None, case_fold_match=False):
        if test_objects is None:
            test_objects = {
                Parameter: {
                    'test_id': Parameter(),
                    'x_id': Parameter(),
                },
                SubFunction: {
                    'Observable': LinearSubFunction(),
                    'duped_id': LinearSubFunction(),
                },
                LinearSubFunction: {
                    'test_id': SubFunction(),
                    'duped_id': SubFunction(),
                },
            }
        parsed_expr = ParsedExpression(model_type, 'attr', expr, test_objects)
        obj_tables_tokens, related_objects, _ = parsed_expr.tokenize(case_fold_match=case_fold_match)
        self.assertEqual(parsed_expr.errors, [])
        self.assertEqual(obj_tables_tokens, expected_wc_tokens)
        for obj_types in test_objects:
            if obj_types in expected_related_objs.keys():
                self.assertEqual(related_objects[obj_types], expected_related_objs[obj_types])
            else:
                self.assertEqual(related_objects[obj_types], {})

    def extract_from_objects(self, objects, type_id_pairs):
        d = {}
        for obj_type, id in type_id_pairs:
            if obj_type not in d:
                d[obj_type] = {}
            d[obj_type][id] = objects[obj_type][id]
        return d

    def test_non_identifier_tokens(self):
        expr = ' 7 * ( 5 - 3 ) / 2'
        expected_wc_tokens = [
            ObjTablesToken(code=ObjTablesTokenCodes.number, token_string='7'),
            ObjTablesToken(code=ObjTablesTokenCodes.op, token_string='*'),
            ObjTablesToken(code=ObjTablesTokenCodes.op, token_string='('),
            ObjTablesToken(code=ObjTablesTokenCodes.number, token_string='5'),
            ObjTablesToken(code=ObjTablesTokenCodes.op, token_string='-'),
            ObjTablesToken(code=ObjTablesTokenCodes.number, token_string='3'),
            ObjTablesToken(code=ObjTablesTokenCodes.op, token_string=')'),
            ObjTablesToken(code=ObjTablesTokenCodes.op, token_string='/'),
            ObjTablesToken(code=ObjTablesTokenCodes.number, token_string='2'),
        ]
        self.do_tokenize_id_test(expr, expected_wc_tokens, {})

    def test_tokenize_w_ids(self):
        # test _get_related_obj_id
        expr = 'test_id'
        sub_func = SubFunction(id=expr)
        objs = {
            SubFunction: {
                expr: sub_func,
                'duped_id': SubFunction(),
            },
            Parameter: {
                'duped_id': Parameter(),
            },
        }
        expected_wc_tokens = \
            [ObjTablesToken(ObjTablesTokenCodes.obj_id, expr, SubFunction,
                            expr, sub_func)]
        expected_related_objs = self.extract_from_objects(objs, [(SubFunction, expr)])
        self.do_tokenize_id_test(expr, expected_wc_tokens, expected_related_objs, test_objects=objs)

        # test _get_disambiguated_id
        expr = 'Parameter.duped_id + 2*SubFunction.duped_id'
        expected_wc_tokens = [
            ObjTablesToken(ObjTablesTokenCodes.obj_id, 'Parameter.duped_id', Parameter, 'duped_id',
                           objs[Parameter]['duped_id']),
            ObjTablesToken(ObjTablesTokenCodes.op, '+'),
            ObjTablesToken(ObjTablesTokenCodes.number, '2'),
            ObjTablesToken(ObjTablesTokenCodes.op, '*'),
            ObjTablesToken(ObjTablesTokenCodes.obj_id, 'SubFunction.duped_id', SubFunction, 'duped_id',
                           objs[SubFunction]['duped_id']),
        ]
        expected_related_objs = self.extract_from_objects(objs, [(Parameter, 'duped_id'),
                                                                 (SubFunction, 'duped_id')])
        self.do_tokenize_id_test(expr, expected_wc_tokens, expected_related_objs, test_objects=objs)

        # test _get_func_call_id
        expr = 'log(3) + func_1 - SubFunction.Function'
        objs = {SubFunction: {'func_1': SubFunction(), 'Function': SubFunction()}}
        expected_wc_tokens = [
            ObjTablesToken(code=ObjTablesTokenCodes.math_func_id, token_string='log'),
            ObjTablesToken(ObjTablesTokenCodes.op, '('),
            ObjTablesToken(ObjTablesTokenCodes.number, '3'),
            ObjTablesToken(ObjTablesTokenCodes.op, ')'),
            ObjTablesToken(ObjTablesTokenCodes.op, '+'),
            ObjTablesToken(ObjTablesTokenCodes.obj_id, 'func_1', SubFunction, 'func_1',
                           objs[SubFunction]['func_1']),
            ObjTablesToken(ObjTablesTokenCodes.op, '-'),
            ObjTablesToken(ObjTablesTokenCodes.obj_id, 'SubFunction.Function', SubFunction, 'Function',
                           objs[SubFunction]['Function'])
        ]
        expected_related_objs = self.extract_from_objects(objs,
                                                          [(SubFunction, 'func_1'), (SubFunction, 'Function')])
        self.do_tokenize_id_test(expr, expected_wc_tokens, expected_related_objs, test_objects=objs)

        # test case_fold_match=True for _get_related_obj_id and _get_disambiguated_id
        expr = 'TEST_ID - SubFunction.DUPED_ID'
        objs = {
            SubFunction: {'test_id': SubFunction(), 'duped_id': SubFunction()},
            LinearSubFunction: {'duped_id': LinearSubFunction()},
        }
        expected_wc_tokens = [
            ObjTablesToken(ObjTablesTokenCodes.obj_id, 'TEST_ID', SubFunction, 'test_id',
                           objs[SubFunction]['test_id']),
            ObjTablesToken(ObjTablesTokenCodes.op, '-'),
            ObjTablesToken(ObjTablesTokenCodes.obj_id, 'SubFunction.DUPED_ID', SubFunction, 'duped_id',
                           objs[SubFunction]['duped_id']),
        ]
        expected_related_objs = self.extract_from_objects(objs, [(SubFunction, 'duped_id'),
                                                                 (SubFunction, 'test_id')])
        self.do_tokenize_id_test(expr, expected_wc_tokens, expected_related_objs, case_fold_match=True, test_objects=objs)

    def test_tokenize_w_multiple_ids(self):
        # at idx==0 match more than one of these _get_related_obj_id(), _get_disambiguated_id(), _get_func_call_id()
        # test _get_related_obj_id and _get_disambiguated_id'
        test_objects = {
            LinearSubFunction: {'SubFunction': SubFunction()},
            SubFunction: {'test_id': LinearSubFunction()}
        }
        expr = 'SubFunction.test_id'
        expected_wc_tokens = [
            ObjTablesToken(ObjTablesTokenCodes.obj_id, expr, SubFunction, 'test_id',
                           test_objects[SubFunction]['test_id'])
        ]
        expected_related_objs = self.extract_from_objects(test_objects, [(SubFunction, 'test_id')])
        self.do_tokenize_id_test(expr, expected_wc_tokens, expected_related_objs,
                                 test_objects=test_objects)

        # test _get_related_obj_id and _get_func_call_id'
        test_objects = {
            SubFunction: {'Function': Parameter()},
            LinearSubFunction: {'fun_2': Function()}
        }
        expr = 'LinearSubFunction.fun_2'
        expected_wc_tokens = [
            ObjTablesToken(ObjTablesTokenCodes.obj_id, expr, LinearSubFunction, 'fun_2',
                           test_objects[LinearSubFunction]['fun_2'])
        ]
        expected_related_objs = self.extract_from_objects(test_objects, [(LinearSubFunction, 'fun_2')])
        self.do_tokenize_id_test(expr, expected_wc_tokens, expected_related_objs,
                                 test_objects=test_objects)

    def do_tokenize_error_test(self, expr, expected_errors, model_type=FunctionExpression, test_objects=None):
        if test_objects is None:
            test_objects = {
                SubFunction: {'SubFunction': SubFunction()},
                LinearSubFunction: {'SubFunction': LinearSubFunction()},
            }
        parsed_expr = ParsedExpression(model_type, 'attr', expr, test_objects)
        sb_none, _, errors = parsed_expr.tokenize()
        self.assertEqual(sb_none, None)
        # expected_errors is a list of lists of strings that should match the actual errors
        expected_errors = [self.esc_re_center(ee) for ee in expected_errors]
        self.assertEqual(len(errors), len(expected_errors),
                         "Counts differ: num errors {} != Num expected errors {}".format(
            len(errors), len(expected_errors)))
        expected_errors_found = {}
        for expected_error in expected_errors:
            expected_errors_found[expected_error] = False
        for error in errors:
            for expected_error in expected_errors:
                if re.match(expected_error, error):
                    if expected_errors_found[expected_error]:
                        self.fail("Expected error '{}' matches again".format(expected_error))
                    expected_errors_found[expected_error] = True
        for expected_error, status in expected_errors_found.items():
            self.assertTrue(status, "Expected error '{}' not found in errors".format(expected_error))

    def test_tokenize_errors(self):
        bad_id = 'no_such_id'
        self.do_tokenize_error_test(
            bad_id,
            [["contains the identifier(s) '{}', which aren't the id(s) of an object".format(bad_id)]])
        bad_id = 'SubFunction.no_such_observable'
        self.do_tokenize_error_test(
            bad_id,
            [["contains multiple model object id matches: 'SubFunction' as a LinearSubFunction id, 'SubFunction' as a SubFunction id"],
             ["contains '{}', but '{}'".format(bad_id, bad_id.split('.')[1]), "is not the id of a"]])
        bad_id = 'no_such_function'
        bad_fn_name = bad_id
        self.do_tokenize_error_test(
            bad_fn_name,
            [["contains the identifier(s) '{}', which aren't the id(s) of an object".format(bad_id)]])
        bad_id = 'LinearSubFunction'
        bad_fn_name = bad_id+'.no_such_function2'
        self.do_tokenize_error_test(
            bad_fn_name,
            [["contains the identifier(s) '{}', which aren't the id(s) of an object".format(bad_id)],
             ["contains '{}', but '{}'".format(bad_fn_name, bad_fn_name.split('.')[1]), "is not the id of a"]])

        expr, error = FunctionExpression.deserialize('p_1 + p_2', {
            Parameter: {'p_1': Parameter(id='p_1'), 'p_2': Parameter(id='p_2'), }
        })
        assert error is None, str(error)
        expr._parsed_expression.expression = ''
        rv = expr._parsed_expression.tokenize()
        self.assertEqual(rv[0], None)
        self.assertEqual(rv[1], None)
        self.assertIn('Expression cannot be empty', rv[2])

    def test_str(self):
        expr = 'func_1 + LinearSubFunction.func_2'
        parsed_expr = self.make_parsed_expr(expr, objects={
            SubFunction: {'func_1': SubFunction()},
            LinearSubFunction: {'func_2': LinearSubFunction()},
        })
        self.assertIn(expr, str(parsed_expr))
        self.assertIn('errors: []', str(parsed_expr))
        self.assertIn('obj_tables_tokens: []', str(parsed_expr))
        parsed_expr.tokenize()
        self.assertIn(expr, str(parsed_expr))
        self.assertIn('errors: []', str(parsed_expr))
        self.assertIn('obj_tables_tokens: [ObjTablesToken', str(parsed_expr))

    def test_model_class_lacks_meta(self):
        class Foo(object):
            pass
        objects = {
            Foo: {'foo_1': Foo(), 'foo_2': Foo()}
        }
        with self.assertRaisesRegex(ParsedExpressionError,
                                    "model_cls 'Foo' is not a subclass of Model"):
            ParsedExpression(Foo, 'expr_attr', '', objects)

    def do_test_eval(self, expr, parent_type, obj_type, related_obj_val, expected_val):
        objects = {
            Parameter: {
                'p_1': Parameter(id='p_1', value=1.),
                'p_2': Parameter(id='p_2', value=2.),
                '1p': Parameter(id='1p', value=3.),
            },
            Species: {
                's_1[c_1]': Species(id='s_1[c_1]'),
                's_2[c_2]': Species(id='s_2[c_2]'),
            },
            SubFunction: {
                'func_1': SubFunction(id='func_1'),
            },
        }
        objects[SubFunction]['func_1'].expression, error = SubFunctionExpression.deserialize('2 * p_2', objects)
        assert error is None, str(error)

        obj, error = Expression.deserialize(obj_type, expr, objects)
        assert error is None, str(error)
        parsed_expr = obj._parsed_expression
        parent = parent_type(expression=obj)
        evaled_val = parsed_expr.test_eval({Species: related_obj_val})
        self.assertEqual(expected_val, evaled_val)

    def test_parsed_expression_compile_error(self):
        expr = '3 + 5 * 6'
        parsed_expr = ParsedExpression(FunctionExpression, 'attr', expr, {})
        parsed_expr.tokenize()
        self.assertEqual(parsed_expr.errors, [])

        parsed_expr._compile()

        parsed_expr._obj_tables_tokens = None
        with self.assertRaisesRegex(ParsedExpressionError, 'not been successfully tokenized'):
            parsed_expr._compile()

    def test_test_eval(self):
        self.do_test_eval('p_1', Function, FunctionExpression, 1., 1.)
        self.do_test_eval('3 * p_1', Function, FunctionExpression, 1., 3.)
        self.do_test_eval('3 * p_2', Function, FunctionExpression, 1., 6.)
        self.do_test_eval('s_1[c_1]', Function, FunctionExpression, 1., 1.)
        self.do_test_eval('s_1[c_1]', Function, FunctionExpression, 2., 2.)
        self.do_test_eval('2 * s_1[c_1]', Function, FunctionExpression, 2., 4.)
        self.do_test_eval('func_1', Function, FunctionExpression, 1., 4.)
        self.do_test_eval('p_1 + func_1', Function, FunctionExpression, 1., 5.)
        self.do_test_eval('1p', Function, FunctionExpression, 1., 3.)
        self.do_test_eval('p_1 * 1p', Function, FunctionExpression, 1., 3.)
        self.do_test_eval('p_1 * 1p + func_1', Function, FunctionExpression, 1., 7.)

        # test combination of ObjTablesTokenCodes
        expected_val = 4 * 1. + pow(2, 2.) + 4.
        self.do_test_eval('4 * p_1 + pow(2, p_2) + func_1', Function, FunctionExpression,
                          None, expected_val)

        # test different model classes
        expected_val = 4 * 1. + pow(2, 2.)
        self.do_test_eval('4 * p_1 + pow(2, p_2)', SubFunction, SubFunctionExpression,
                          None, expected_val)

        # test different exceptions
        # syntax error
        model_type = FunctionExpression
        parsed_expr = self.make_parsed_expr('4 *', obj_type=model_type)
        rv = parsed_expr.tokenize()
        self.assertEqual(rv[0], None)
        self.assertEqual(rv[1], None)
        self.assertRegex(str(rv[2]), 'SyntaxError')

        # expression that could not be serialized
        expr = 'foo(6)'
        parsed_expr = self.make_parsed_expr(expr, obj_type=model_type)
        parsed_expr.tokenize()
        model = model_type(expression=parsed_expr)
        with self.assertRaisesRegex(ParsedExpressionError,
                                    re.escape("Cannot evaluate '{}', as it not been "
                                              "successfully compiled".format(expr))):
            parsed_expr.test_eval()

    def test_eval_with_units(self):
        func = Function(id='func', units=unit_registry.parse_units('g l^-1'))
        func.expression, error = FunctionExpression.deserialize('p_1 / p_2', {
            Parameter: {
                'p_1': Parameter(id='p_1', value=2., units=unit_registry.parse_units('g')),
                'p_2': Parameter(id='p_2', value=5., units=unit_registry.parse_units('l')),
            }
        })
        assert error is None, str(error)

        rv = func.expression._parsed_expression.eval({}, with_units=True)
        self.assertEqual(rv.magnitude, 0.4)
        self.assertEqual(rv.units, unit_registry.parse_units('g l^-1'))

        func.expression.parameters.get_one(id='p_1').units = unit_registry.parse_units('g')
        func.expression.parameters.get_one(id='p_2').units = unit_registry.parse_units('l')

    def test_eval_with_units_and_boolean(self):
        func_1 = SubFunction(id='func_1', units=unit_registry.parse_units('dimensionless'))
        func_1.expression, error = SubFunctionExpression.deserialize('p_1 < p_2', {
            Parameter: {
                'p_1': Parameter(id='p_1', value=2., units=unit_registry.parse_units('g')),
                'p_2': Parameter(id='p_2', value=5., units=unit_registry.parse_units('l')),
            }
        })
        assert error is None, str(error)

        func_2 = Function(id='func_2', units=unit_registry.parse_units('g l^-1'))
        func_2.expression, error = FunctionExpression.deserialize('(p_3 / p_4) * func_1', {
            Parameter: {
                'p_3': Parameter(id='p_3', value=2., units=unit_registry.parse_units('g')),
                'p_4': Parameter(id='p_4', value=5., units=unit_registry.parse_units('l')),
            },
            SubFunction: {
                func_1.id: func_1,
            },
        })
        assert error is None, str(error)

        rv = func_2.expression._parsed_expression.eval({}, with_units=True)
        self.assertEqual(rv.magnitude, 0.4)
        self.assertEqual(rv.units, unit_registry.parse_units('g l^-1'))

        func_1.expression.parameters.get_one(id='p_1').value = 10.
        rv = func_2.expression._parsed_expression.eval({}, with_units=True)
        self.assertEqual(rv.magnitude, 0.)
        self.assertEqual(rv.units, unit_registry.parse_units('g l^-1'))

    def test_eval_error(self):
        func = Function(id='func', units=unit_registry.parse_units('g l^-1'))
        func.expression, error = FunctionExpression.deserialize('p_1 / p_2', {
            Parameter: {
                'p_1': Parameter(id='p_1', value=2., units=unit_registry.parse_units('g')),
                'p_2': Parameter(id='p_2', value=5., units=unit_registry.parse_units('l')),
            }
        })
        assert error is None, str(error)

        func.expression._parsed_expression._compiled_expression = '1 *'
        with self.assertRaisesRegex(ParsedExpressionError, 'SyntaxError'):
            func.expression._parsed_expression.eval({})

        func.expression._parsed_expression._compiled_expression = 'p_3'
        with self.assertRaisesRegex(ParsedExpressionError, 'NameError'):
            func.expression._parsed_expression.eval({})

        func.expression._parsed_expression._compiled_expression = '1 / 0'
        with self.assertRaisesRegex(ParsedExpressionError, 'Exception'):
            func.expression._parsed_expression.eval({})

        func = Function(id='func', units=unit_registry.parse_units('g l^-1'))
        func.expression, error = FunctionExpression.deserialize('p_1 / p_2', {
            Parameter: {
                'p_1': Parameter(id='p_1', value=2., units=None),
                'p_2': Parameter(id='p_2', value=5., units=unit_registry.parse_units('l')),
            }
        })
        assert error is None, str(error)
        with self.assertRaisesRegex(ParsedExpressionError, 'Units must be defined'):
            func.expression._parsed_expression.eval({}, with_units=True)

        func = Function(id='func', units=unit_registry.parse_units('g l^-1'))
        func.expression, error = FunctionExpression.deserialize('p_1 / p_2', {
            Parameter: {
                'p_1': Parameter(id='p_1', value=2., units='g'),
                'p_2': Parameter(id='p_2', value=5., units=unit_registry.parse_units('l')),
            }
        })
        assert error is None, str(error)
        with self.assertRaisesRegex(ParsedExpressionError, 'Unsupported units'):
            func.expression._parsed_expression.eval({}, with_units=True)

    def test___prep_expr_for_tokenization(self):
        parsed_expr = ParsedExpression

        # substitutes tokens that begin with numbers
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0abc'), '__digit__0abc')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0abc + x'), '__digit__0abc + x')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('x + 0abc'), 'x + __digit__0abc')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0abc / 1def2'), '__digit__0abc / __digit__1def2')

        # doesn't substitute numbers
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0'), '0')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0.1'), '0.1')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('-0.2'), '-0.2')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('+0.3'), '+0.3')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0 + 1'), '0 + 1')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('x * 0 + 1'), 'x * 0 + 1')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('x *0 + 1'), 'x *0 + 1')

        # doesn't substitute exponential notation
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('2e1'), '2e1')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('2.1e1'), '2.1e1')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('2e+1'), '2e+1')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('2e-1'), '2e-1')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('2e1.1'), '2e1.1')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('2E1'), '2E1')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('2e1 + x'), '2e1 + x')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('x + 2e1'), 'x + 2e1')

        # doesn't substitute hexidecimal numbers
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0xff'), '0xff')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0xFF'), '0xFF')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0xAA ** 0xFF'), '0xAA ** 0xFF')

        # combinations
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('0abc/0xAA'),
                         '__digit__0abc/0xAA')
        self.assertEqual(parsed_expr._ParsedExpression__prep_expr_for_tokenization('2e1*0abc/0xAA'),
                         '2e1*__digit__0abc/0xAA')


class ParsedExpressionErrorTestCase(unittest.TestCase):
    def test___init__(self):
        exception = ParsedExpressionError('test message')
        self.assertEqual(exception.args, ('test message',))


class LinearParsedExpressionValidatorTestCase(unittest.TestCase):

    def setUp(self):
        self.test_objects = {
            Parameter: {
                'r': Parameter(id='r'),
                'r_for': Parameter(id='r_for'),
                'r_back': Parameter(id='r_back'),
            }
        }

    @staticmethod
    def clean_astor_expr(tree):
        # remove trailing \n and enclosing parens from astor.to_source(tree)
        source = astor.to_source(tree).strip()
        if source[0] == '(' and source[-1] == ')':
            return source[1:-1]
        return source

    def test_convert_model_id_to_python_id(self):
        lpev = LinearParsedExpressionValidator()
        self.assertEqual(lpev._convert_model_id_to_python_id('good_id_1'), 'good_id_1')
        first_py_id = f"{lpev.VALID_PYTHON_ID_PREFIX}1"
        self.assertEqual(lpev._convert_model_id_to_python_id('class'), first_py_id)
        # get id from id dict
        self.assertEqual(lpev._convert_model_id_to_python_id('class'), first_py_id)
        second_py_id = f"{lpev.VALID_PYTHON_ID_PREFIX}2"
        self.assertEqual(lpev._convert_model_id_to_python_id('ATP[c]'), second_py_id)

    def test_expr_with_python_ids(self):
        lpev = LinearParsedExpressionValidator()
        test_objects = {
            Parameter: {
                'r': Parameter(),
            }
        }
        expr = '2 * r'
        parsed_expr = ParsedExpression(FunctionExpression, 'attr', expr, test_objects)
        parsed_expr.tokenize()
        self.assertEqual(lpev._expr_with_python_ids(parsed_expr), expr)

    def test__init(self):
        with self.assertRaisesRegex(ValueError, 'Cannot validate empty expression'):
            LinearParsedExpressionValidator()._init(' \n')

    def test_validate_methods(self):
        valid, error = LinearParsedExpressionValidator()._init('1 +')._validate_syntax()
        self.assertFalse(valid)
        self.assertIn('Python syntax error', error)

        valid, error = LinearParsedExpressionValidator()._init('1 + x * 3')._validate_syntax()
        self.assertTrue(valid)
        self.assertTrue(error is None)

        lpev = LinearParsedExpressionValidator()._init('3**2 + (2, 4)[0]')
        lpev._validate_syntax()
        valid, error = lpev._validate_node_types()
        self.assertFalse(valid)
        self.assertIn('Pow', error)
        self.assertIn('Subscript', error)

        lpev = LinearParsedExpressionValidator()._init('-1 + +3 - 1.1E3 + id - 4*(id2 + 3)')
        lpev._validate_syntax()
        valid, error = lpev._validate_node_types()
        self.assertTrue(valid)
        self.assertTrue(error is None)
        valid, error = lpev._validate_nums()
        self.assertTrue(valid)
        self.assertTrue(error is None)

        lpev = LinearParsedExpressionValidator()._init('-1 + 3j')
        lpev._validate_syntax()
        valid, error = lpev._validate_nums()
        self.assertFalse(valid)
        self.assertIn("can't convert complex to float", error)

    def test_ast_transformations(self):
        # test _dist_mult
        init_and_expected_exprs = [('x*(3 + 5) + (x - y + z)*3', 'x * 3 + x * 5 + (x * 3 - y * 3 + z * 3)'),
                                   ('5*c * (-1 + d)', '5 * c * -1 + 5 * c * d'),
                                   ('(a + b)*(5 - 1)', 'a * 5 - a * 1 + (b * 5 - b * 1)'),
        ]
        for expr, distrib_math_expr in init_and_expected_exprs:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            lpev._dist_mult()
            self.assertEqual(self.clean_astor_expr(lpev.tree), distrib_math_expr)

        # test _remove_unary_operators
        expr_and_expt_expr_wo_unary_ops = [('2', '2'),
                                           ('+2', '2'),
                                           ('+++3', '3'),
                                           ('-+-4', '-1 * (-1 * 4)'),
                                           ('-x', '-1 * x'),
                                           ('-(x + -3)*+y', '-1 * (x + -1 * 3) * y'),
        ]
        for expr, expt_expr_wo_unary_ops in expr_and_expt_expr_wo_unary_ops:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            lpev._remove_unary_operators()
            self.assertEqual(self.clean_astor_expr(lpev.tree), expt_expr_wo_unary_ops)

        # test _move_coeffs_to_left and _multiply_numbers
        expr_and_expected_results = [('r_for*5 - 2*r_back*3 * 8',
                                      '5 * r_for - 8 * (3 * (2 * r_back))',
                                      '5 * r_for - 48 * r_back'),
                                     ('2 * 3 * 5 * x',
                                     '5 * (2 * 3) * x',
                                     '30 * x'),
        ]
        for expr, expected_coeffs_on_left, expected_mult_constants in expr_and_expected_results:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            lpev._move_coeffs_to_left()
            self.assertEqual(self.clean_astor_expr(lpev.tree), expected_coeffs_on_left)
            lpev._multiply_numbers()
            self.assertEqual(self.clean_astor_expr(lpev.tree), expected_mult_constants)

        # test _remove_subtraction and _multiply_numbers
        expr_and_expected_results = [('0 - x', '0 + -1 * x', '0 + -1 * x'),
                                     ('0 - 4', '0 + -1 * 4', '0 + -4'),
                                     ('x - (3 + y)', 'x + (-1 * 3 + -1 * y)', 'x + (-3 + -1 * y)'),
                                     ('x - (3 - y)', 'x + (-1 * 3 + -1 * (-1 * y))', 'x + (-3 + 1 * y)'),
                                     ('x - (3 * y)', 'x + -1 * 3 * y', 'x + -3 * y'),
        ]
        for expr, expected_expr_wo_sub, expected_expr_mult_nums in expr_and_expected_results:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            lpev._remove_subtraction()
            self.assertEqual(self.clean_astor_expr(lpev.tree), expected_expr_wo_sub)
            lpev._multiply_numbers()
            self.assertEqual(self.clean_astor_expr(lpev.tree), expected_expr_mult_nums)

        # test _multiply_numbers in one call to MultiplyNums().visit(self.tree)
        expr = '(5 * 7) * (2 * (3 * x))'
        expected_expr_mult_nums = '210 * x'
        lpev = LinearParsedExpressionValidator()._init(expr)
        lpev._validate_syntax()
        lpev._multiply_numbers()
        self.assertEqual(self.clean_astor_expr(lpev.tree), expected_expr_mult_nums)

    def test_num_of_variables_in_products(self):
        expr_and_expected_vars_in_product = [('x * y * (3 * z)', 3),
                                             ('3*(6 * 7) * (3 + 5)', 0),
        ]
        for expr, expected_vars_in_product in expr_and_expected_vars_in_product:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            self.assertEqual(lpev._num_of_variables_in_a_product(lpev.tree.body), expected_vars_in_product)

        expr_and_expt_max_num_vars_in_a_product = [('3*(6 * 7) * (3 + 5)', 0),
                                                   ('3 * z + x * y * (3 * z) - 2 *x', 3),
                                                   ('3 + x * (2 + -x + z) - (a + 3*b * (5*c * (-1 + d)))', 3),
        ]
        for expr, expt_max_num_vars_in_a_product in expr_and_expt_max_num_vars_in_a_product:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            lpev._dist_mult()
            self.assertEqual(lpev._max_num_variables_in_a_product(), expt_max_num_vars_in_a_product)

            expr_has_products_of_variables = lpev._expr_has_products_of_variables()
            if expt_max_num_vars_in_a_product <= 1:
                self.assertFalse(expr_has_products_of_variables)
            else:
                self.assertTrue(expr_has_products_of_variables)

    def test__expr_has_a_constant(self):
        expr_and_expt_constant_terms = [('2', True),
                                        ('z', False),
                                        ('3*x + y', False),
                                        ('(x + 3)*y', False),
                                        ('(x + 3)*4', True),
                                        ('(a + -3)*(5 - x)', True),
        ]
        for expr, expt_constant_terms in expr_and_expt_constant_terms:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            lpev._remove_unary_operators()
            lpev._multiply_numbers()
            lpev._dist_mult()
            lpev._multiply_numbers()
            self.assertEqual(lpev._expr_has_a_constant(), expt_constant_terms)

    def test__validate_failures(self):
        not_linear_exprs = [('not Python syntax -', "Python syntax error"),
                            # contains terms not allowed in a linear expression, such as **
                            ('3**2 + (2, 4)[0]', "contains invalid terms"),
                            # contains 3j, a number that can't be coerced to float
                            ('-1 + 3j', "can't convert complex to float"),
                            ('(a + -3) * 2', "contains constant term(s)"),
                            ('3 * z + x * y * (3 * z)', "contains product(s) of variables"),
                            ('(r_for - r_bak) * 5', "contains a constant right of a var in a product"),
        ]
        for not_linear_expr, exp_error in not_linear_exprs:
            lpev = LinearParsedExpressionValidator()
            lpev.expression = not_linear_expr
            valid, error = lpev._validate()
            self.assertFalse(valid)
            self.assertIn(exp_error, error)

    def test__validate_split_reactions(self):
        # test examples of split reactions in dFBA objective expressions in wc_lang
        expr_and_expt_validity = [('(r_for - r_back)', True),
                                  ('r + 2 * (r_for - r_back)', True),
                                  ('r - 2 * (r_for - r_back)', True),
                                  ('r + -2 * (r_for - r_back)', True),
                                  ('r + (r_for - r_back) * 2', False),
        ]
        for expr, expt_validity in expr_and_expt_validity:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate()
            valid, error = LinearParsedExpressionValidator()._init(expr)._validate()
            self.assertEqual(valid, expt_validity)

    def test_validate(self):
        linear_expression = '3 * r - 4*(r_for - r_back)'
        parsed_expr = ParsedExpression(FunctionExpression, 'attr', linear_expression, self.test_objects)
        parsed_expr.tokenize()

        valid, error = LinearParsedExpressionValidator().validate(parsed_expr)
        self.assertTrue(valid)
        self.assertTrue(error is None)

    @unittest.skip("Runs under 'pytest tests/math/test_math_expression.py' but not 'pytest tests/'")
    def test_validate_exception(self):
        linear_expression = base_linear_expression = '3 * r - 4 * r_back + 2 * r_for'
        # blow up size of expression to raise RecursionError
        with self.assertRaisesRegex(ParsedExpressionError,
                                    'RecursionError in ast or LinearParsedExpressionValidator._validate'):
            while True:
                parsed_expr = ParsedExpression(FunctionExpression, 'attr', linear_expression, self.test_objects)
                parsed_expr.tokenize()
                valid, error = LinearParsedExpressionValidator().validate(parsed_expr)
                linear_expression = f"{linear_expression} + {base_linear_expression}"
                gc.collect()

    def test__expr_has_constants_right_of_variables(self):
    
        # test _product_has_name
        expr_and_expt_product_has_name = [('2', False),
                                          ('z', True),
                                          ('3 * x * -3', True),
                                          ('3 * (5 * 2 * (x))', True),
                                          ('3 * (5 * 2 * (7))', False),
        ]
        for expr, expt_product_has_name in expr_and_expt_product_has_name:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            lpev._remove_unary_operators()
            lpev._dist_mult()
            self.assertEqual(LinearParsedExpressionValidator._product_has_name(lpev.tree.body), expt_product_has_name)

        # test _product_has_num
        expr_and_expt_product_has_num = [('2', True),
                                         ('z', False),
                                         ('3 * x * -3', True),
                                         ('3 * (5 * 2 * (x))', True),
                                         ('3 * (5 * 2) + 3', False),
        ]
        for expr, expt_product_has_num in expr_and_expt_product_has_num:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            lpev._remove_unary_operators()
            lpev._dist_mult()
            self.assertEqual(LinearParsedExpressionValidator._product_has_num(lpev.tree.body), expt_product_has_num)

        # test _expr_has_constant_right_of_vars
        expr_and_expt_constant_right_of_vars = [('2', False),
                                                ('z', False),
                                                ('3 * x * -3', True),
                                                ('3 * (5 * 2 * (x))', False),
                                                ('3 * (5 * 2) + 3', False),
                                                ('(a + -3) * (5 - x)', True),
                                                ('(r_for - r_bak) * 5', True),
        ]
        for expr, expt_constant_right_of_vars in expr_and_expt_constant_right_of_vars:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            lpev._remove_unary_operators()
            lpev._dist_mult()
            self.assertEqual(lpev._expr_has_constant_right_of_vars(), expt_constant_right_of_vars)

    def test_get_cls_and_model(self):
        linear_expression = '3 * r - 4*(r_for - r_back)'
        parsed_expr = ParsedExpression(FunctionExpression, 'attr', linear_expression, self.test_objects)
        parsed_expr.tokenize()
        lpev = LinearParsedExpressionValidator()
        valid, _ = lpev.validate(parsed_expr)
        self.assertTrue(valid)
        self.assertEqual(lpev.get_cls_and_model('r_back'), (Parameter, self.test_objects[Parameter]['r_back']))
        self.assertEqual(lpev.get_cls_and_model('r'), (Parameter, self.test_objects[Parameter]['r']))

        self.test_objects[SubFunction] = {'r': SubFunction(id='r'),
                                          'bm_1': SubFunction(id='bm_1'),
                                         }
        linear_expression = '3 * Parameter.r + SubFunction.r'
        parsed_expr = ParsedExpression(FunctionExpression, 'attr', linear_expression, self.test_objects)
        parsed_expr.tokenize()
        lpev = LinearParsedExpressionValidator()
        valid, _ = lpev.validate(parsed_expr, set_linear_coeffs=False)
        self.assertTrue(valid)
        with self.assertRaisesRegex(ParsedExpressionError, 'multiple models with id'):
            lpev.get_cls_and_model('r')

    def test__get_coeffs_for_vars(self):
        expr_and_expt_coeffs_4_vars = [('x',
                                        [(1.0, 'x')]),
                                       ('x + y',
                                        [(1.0, 'x'), (1.0, 'y')]),
                                       ('x + 2 * y',
                                        [(1.0, 'x'), (2.0, 'y')]),
                                       ('2 * x + y',
                                        [(2.0, 'x'), (1.0, 'y')]),
                                       ('a + b + -2 * c + d + e + 4 * f',
                                        [(1.0, 'a'), (1.0, 'b'), (-2.0, 'c'), (1.0, 'd'), (1.0, 'e'), (4.0, 'f')]),
                                       ('3 * r - 4*(r_for - r_back)',
                                        [(3.0, 'r'), (4.0, 'r_back'), (-4.0, 'r_for')]),
        ]
        for expr, expt_coeffs_4_vars in expr_and_expt_coeffs_4_vars:
            lpev = LinearParsedExpressionValidator()._init(expr)
            lpev._validate_syntax()
            valid, _ = lpev._validate()
            self.assertTrue(valid)
            self.assertEqual(set(lpev._get_coeffs_for_vars()), set(expt_coeffs_4_vars))

    def test_set_lin_coeffs(self):
        linear_expr_and_expt_lin_coeffs = [('r',
                                       [('r', 1.0)]),
                                      ('3 * r',
                                       [('r', 3.0)]),
                                      ('(r_for - r_back)',
                                       [('r_for', 1.0), ('r_back', -1.0)]),
                                      ('r + 2 * r_for - r_back',
                                       [('r', 1.0), ('r_for', 2.0), ('r_back', -1.0)]),
                                      ('r - 2 * r_for - r_back',
                                       [('r', 1.0), ('r_for', -2.0), ('r_back', -1.0)]),
                                      ('r + -2 * r_for - r_back',
                                       [('r', 1.0), ('r_for', -2.0), ('r_back', -1.0)]),
                                      ('3 * r - 4*(r_for - r_back)',
                                       [('r', 3.0), ('r_for', -4.0), ('r_back', 4.0)]),
                                      ('3 * r - r + -r',
                                       [('r', 1.0)]),
                                      ('(1+2) * r - (3 + 5) * -1 * r + r',
                                       [('r', 12.0)]),
        ]
        for linear_expr, expt_lin_coeffs in linear_expr_and_expt_lin_coeffs:
            parsed_expr = ParsedExpression(FunctionExpression, 'attr', linear_expr, self.test_objects)
            parsed_expr.tokenize()
            lpev = LinearParsedExpressionValidator()
            valid, _ = lpev.validate(parsed_expr)
            self.assertTrue(valid)
            lpev._set_lin_coeffs()
            lin_coeffs = set()
            for cls in lpev.parsed_expression.lin_coeffs:
                for model, coeff in lpev.parsed_expression.lin_coeffs[cls].items():
                    lin_coeffs.add((model.id, coeff))
            self.assertEqual(lin_coeffs, set(expt_lin_coeffs))


class RandomExpression(object):
    """ Generate random expressions for testing LinearParsedExpressionValidator
    """
    # TODO (APG): finish and use to test LinearParsedExpressionValidator

    rel_prob_token = {'name': 3,
                      'int': 3,
                      '+': 2,
                      '-': 2,
                      '*': 2,
                      'UnaryPlus': 1,
                      'UnaryMinus': 1,
    }
    delta_terms_token = {'name': +1,
                         'int': +1,
                         '+': -1,
                         '-': -1,
                         '*': -1,
                         'UnaryPlus': 0,
                         'UnaryMinus': 0,
    }

    def random_rpn_expr(self, **kwargs):
        defaults = dict(n_names=4,
                        min_int=-2,
                        max_int=5,
                        n_init_symbols=2,
                        max_num_symbols=5
        )
        for arg, default_val in defaults.items():
            if arg not in kwargs:
                kwargs[arg] = defaults[arg]

        def rand_int():
            return random.randint(kwargs['min_int'], kwargs['max_int'])

        names = [f"var_{i}" for i in range(kwargs['n_names'])]
        def rand_name():
            return random.choice(names)

        rpn_tokens = []
        # number free terms in rpn_tokens
        n_free_terms = 0

        # initialize with initial symbols
        for i in range(kwargs['n_init_symbols']):
            n_free_terms += 1
            total_p = self.rel_prob_token['name'] + self.rel_prob_token['int']
            if random.random() < self.rel_prob_token['name']/total_p:
                rpn_tokens.append(rand_name())
            else:
                rpn_tokens.append(rand_int())

        # randomly add tokens, up to max_num_symbols
        num_symbols = kwargs['n_init_symbols']
        while num_symbols < kwargs['max_num_symbols']:
            tokens = random.choices(list(self.rel_prob_token), weights=self.rel_prob_token.values())
            token = tokens[0]
            # keep 1 <= n_free_terms
            if 1 == n_free_terms and token in set(['+', '-', '*', ]):
                continue
            if token in set(['name', 'int']):
                num_symbols += 1
            if token == 'name':
                rpn_tokens.append(rand_name())
            elif token == 'int':
                rpn_tokens.append(rand_int())
            else:
                rpn_tokens.append(token)
            n_free_terms += self.delta_terms_token[token]
        # add enough operators to complete expression
        while 0 < n_free_terms:
            tokens = random.choices(list(self.rel_prob_token), weights=self.rel_prob_token.values())
            token = tokens[0]
            if token in set(['+', '-', '*', ]):
                rpn_tokens.append(token)
                n_free_terms += self.delta_terms_token[token]
        return rpn_tokens

    @staticmethod
    def convert_rpn_to_infix(**kwargs):
        """ Use RPN conversion algorithm to generate infix expression
        """


class TestRandomExpression(unittest.TestCase):
    def test(self):
        for i in range(20):
            self.assertTrue(isinstance(RandomExpression().random_rpn_expr(), list))


class CopyTestCase(unittest.TestCase):
    def test(self):
        p_1 = Parameter(id='p_1', value=1.5, units=unit_registry.parse_units('g'))
        p_2 = Parameter(id='p_2', value=2.5, units=unit_registry.parse_units('l'))
        func_1 = Function(id='func_1')
        func_1.expression, error = FunctionExpression.deserialize('p_1 / p_2', {
            Parameter: {p_1.id: p_1, p_2.id: p_2}
        })
        assert error is None, str(error)

        func_2 = func_1.copy()

        self.assertTrue(func_2.is_equal(func_1))
        self.assertEqual(func_2.expression._parsed_expression.related_objects, {
            LinearSubFunction: {},
            Species: {},
            SubFunction: {},
            Parameter: {
                'p_1': func_2.expression.parameters.get_one(id='p_1'),
                'p_2': func_2.expression.parameters.get_one(id='p_2'),
            },
        }
        )
