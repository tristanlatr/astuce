
import ast
from functools import partial
from typing import Any

import pytest

from astuce import nodes
from astuce.exceptions import InferenceError
from . import AstuceTestCase

class Parse__all__Test(AstuceTestCase):

    def test_parse__all__(self):
        ...

# @pytest.mark.parametrize(
#     "statements",
#     [
#         """__all__ = moda_all + modb_all + modc_all + ["CONST_INIT"]""",
#         """__all__ = ["CONST_INIT", *moda_all, *modb_all, *modc_all]""",
#         """
#         __all__ = ["CONST_INIT"]
#         __all__ += moda_all + modb_all + modc_all
#         """,
#         """
#         __all__ = moda_all + modb_all + modc_all
#         __all__ += ["CONST_INIT"]
#         """,
#         """
#         __all__ = ["CONST_INIT"]
#         __all__ += moda_all
#         __all__ += modb_all + modc_all
#         """,
#     ],
# )
# def test_parse_complex__all__assignments(statements):
#     """Check our ability to expand exports based on `__all__` [augmented] assignments.
#     Parameters:
#         statements: Parametrized text containing `__all__` [augmented] assignments.
#     """
#     with temporary_pypackage("package", ["moda.py", "modb.py", "modc.py"]) as tmp_package:
#         tmp_package.path.joinpath("moda.py").write_text("CONST_A = 1\n\n__all__ = ['CONST_A']")
#         tmp_package.path.joinpath("modb.py").write_text("CONST_B = 1\n\n__all__ = ['CONST_B']")
#         tmp_package.path.joinpath("modc.py").write_text("CONST_C = 2\n\n__all__ = ['CONST_C']")
#         code = """
#             from package.moda import *
#             from package.moda import __all__ as moda_all
#             from package.modb import *
#             from package.modb import __all__ as modb_all
#             from package.modc import *
#             from package.modc import __all__ as modc_all
#             CONST_INIT = 0
#         """
#         tmp_package.path.joinpath("__init__.py").write_text(dedent(code) + dedent(statements))

#         loader = GriffeLoader(search_paths=[tmp_package.tmpdir])
#         package = loader.load_module(tmp_package.name)
#         loader.resolve_aliases()

#         assert package.exports == {"CONST_INIT", "CONST_A", "CONST_B", "CONST_C"}

class FirstInfenceTests(AstuceTestCase):
    """
    From astroid basically.
    """

    def test_del1(self) -> None:
        code = "del undefined_attr"
        delete = self.parse(code).body[0]
        self.assertRaises(InferenceError, next, delete.infer())

    def test_del2(self) -> None:
        code = """
            a = 1
            b = a
            del a
            c = a
            a = 2
            d = a
        """
        mod = self.parse(code, __name__)
        
        n = mod.locals["b"][0]
        n_infer = n.infer()
        inferred = next(n_infer)
        self.assertIsInstance(inferred, ast.Constant)
        self.assertEqual(inferred.value, 1)
        self.assertRaises(StopIteration, partial(next, n_infer))
        
        n = mod.locals["c"][0]
        n_infer = n.infer()
        self.assertRaises(InferenceError, partial(next, n_infer))
        
        n = mod.locals["d"][0]
        n_infer = n.infer()
        inferred = next(n_infer)
        self.assertIsInstance(inferred, ast.Constant)
        self.assertEqual(inferred.value, 2)
        self.assertRaises(StopIteration, partial(next, n_infer))

    def test_builtin_types(self) -> None:
        code = """
            l = [1]
            t = (2,)
            d = {}
            s = ''
            s2 = '_'
        """
        mod = self.parse(code)
        n = mod.locals["l"][0]
        inferred = next(n.infer())
        self.assertIsInstance(inferred, ast.List)
        self.assertIsInstance(inferred, nodes.Instance)

        # Not in scope not the moment
        # self.assertEqual(inferred.getitem(ast.Const(0)).value, 1)

        # TODO: uncomment me when we better support builtins
        # self.assertIsInstance(inferred.type_info.classdef, ast.ClassDef)

        self.assertIsInstance(inferred.type_info.type_annotation, ast.Name)
        self.assertEqual(inferred.type_info.type_annotation.id, "list")

        # Not in scope not the moment
        # self.assertIn("append", inferred._proxied.locals)
        
        n = mod.locals["t"][0]
        inferred = next(n.infer())
        self.assertIsInstance(inferred, ast.Tuple)
        self.assertIsInstance(inferred, nodes.Instance)
        self.assertIsInstance(inferred.type_info.type_annotation, ast.Name)
        self.assertEqual(inferred.type_info.type_annotation.id, "tuple")
        # self.assertIsInstance(inferred.type_info.classdef, ast.ClassDef)
        
        # self.assertIsInstance(inferred, Instance)
        # self.assertEqual(inferred.getitem(ast.Const(0)).value, 2)
        # self.assertIsInstance(inferred._proxied, ast.ClassDef)
        # self.assertEqual(inferred._proxied.name, "tuple")
        
        # Dicts not in scope right now, but will be soon.
        # TODO: Add _infer_Dict and co.
        n = mod.locals["d"][0]
        inferred = next(n.infer())
        assert inferred is nodes.Uninferable
        # self.assertIsInstance(inferred, ast.Dict)
        # self.assertIsInstance(inferred, nodes.Instance)
        # self.assertIsInstance(inferred.type_info.type_annotation, ast.Name)
        # self.assertEqual(inferred.type_info.type_annotation.id, "dict")
        # self.assertIsInstance(inferred.type_info.classdef, ast.ClassDef)
        
        # self.assertIsInstance(inferred, Instance)
        # self.assertIsInstance(inferred._proxied, ast.ClassDef)
        # self.assertEqual(inferred._proxied.name, "dict")
        # self.assertIn("get", inferred._proxied.locals)
        
        n = mod.locals["s"][0]
        inferred = next(n.infer())
        self.assertIsInstance(inferred, ast.Constant)
        self.assertIsInstance(inferred, nodes.Instance)
        self.assertIsInstance(inferred.type_info.type_annotation, ast.Name)
        self.assertEqual(inferred.type_info.type_annotation.id, "str")
        # self.assertIsInstance(inferred.type_info.classdef, ast.ClassDef)
        
        # self.assertIsInstance(inferred, Instance)
        # self.assertEqual(inferred.name, "str")
        # self.assertIn("lower", inferred._proxied.locals)
        
        n = mod.locals["s2"][0]
        inferred = next(n.infer())
        self.assertIsInstance(inferred, nodes.Instance)
        self.assertIsInstance(inferred.type_info.type_annotation, ast.Name)
        self.assertEqual(inferred.type_info.type_annotation.id, "str")
        # self.assertIsInstance(inferred.type_info.classdef, ast.ClassDef)
        self.assertEqual(inferred.literal_eval(), "_")

        code = "s = {1}"
        mod = self.parse(code)
        
        n = mod.locals["s"][0]
        inferred = next(n.infer())
        self.assertIsInstance(inferred, ast.Set)
        self.assertIsInstance(inferred, nodes.Instance)
        self.assertIsInstance(inferred.type_info.type_annotation, ast.Name)
        self.assertEqual(inferred.type_info.type_annotation.id, "set")
        # self.assertIsInstance(inferred.type_info.classdef, ast.ClassDef)

        # self.assertIsInstance(inferred, Instance)
        # self.assertEqual(inferred.name, "set")
        # self.assertIn("remove", inferred._proxied.locals)

    def test_simple_subscript(self) -> None:
        return
        code = """
            [1, 2, 3][0] 
            (1, 2, 3)[1] 
            (1, 2, 3)[-1] 
            [1, 2, 3][0] + (2, )[0] + (3, )[-1] 
            e = {'key': 'value'}
            e['key'] 
            "first"[0] 
            
            # TODO: Would be good to support the two lines below
            # list([1, 2, 3])[-1] #@
            # tuple((4, 5, 6))[2] #@

            # Outside out the scope:
            # class A(object):
            #     def __getitem__(self, index):
            #         return index + 42
            # A()[0] #@
            # A()[-1] #@
        """
        statements = self.parse(code).body
        ast_nodes = []
        for s in statements:
            if isinstance(s, ast.Expr):
                ast_nodes.append(s.value)
            else:
                assert isinstance(s, ast.Assign) # dict assign
        expected = [1, 2, 3, 6, "value", "f"]
        assert len(ast_nodes) == len(expected)
        for node, expected_value in zip(ast_nodes, expected):
            inferred = next(node.infer())
            self.assertIsInstance(inferred, ast.Constant)
            self.assertEqual(inferred.value, expected_value)

    def test_simple_tuple(self) -> None:
        module = self.parse(
            """
        a = (1,)
        b = (22,)
        some = a + b #@
        """
        )
        i = next(module.locals["some"][0].infer())
        self.assertIsInstance(i, ast.Tuple)
        self.assertEqual(len(i.elts), 2)
        self.assertEqual(i.elts[0].value, 1)
        self.assertEqual(i.elts[1].value, 22)

# NOT In scope for the moment.
# def test_simple_for(self) -> None:
#     code = """
#         for a in [1, 2, 3]:
#             print (a)
#         for b,c in [(1,2), (3,4)]:
#             print (b)
#             print (c)

#         print ([(d,e) for e,d in ([1,2], [3,4])])
#     """
#     ast = parse(code, __name__)
#     self.assertEqual(
#         [i.value for i in test_utils.get_name_node(ast, "a", -1).infer()], [1, 2, 3]
#     )
#     self.assertEqual(
#         [i.value for i in test_utils.get_name_node(ast, "b", -1).infer()], [1, 3]
#     )
#     self.assertEqual(
#         [i.value for i in test_utils.get_name_node(ast, "c", -1).infer()], [2, 4]
#     )
#     self.assertEqual(
#         [i.value for i in test_utils.get_name_node(ast, "d", -1).infer()], [2, 4]
#     )
#     self.assertEqual(
#         [i.value for i in test_utils.get_name_node(ast, "e", -1).infer()], [1, 3]
#     )

# NOT In scope for the moment.
# def test_simple_for_genexpr(self) -> None:
#     code = """
#         print ((d,e) for e,d in ([1,2], [3,4]))
#     """
#     ast = parse(code, __name__)
#     self.assertEqual(
#         [i.value for i in test_utils.get_name_node(ast, "d", -1).infer()], [2, 4]
#     )
#     self.assertEqual(
#         [i.value for i in test_utils.get_name_node(ast, "e", -1).infer()], [1, 3]
#     )

    def test_unary_not(self) -> None:
        return
        for code in (
            "a = not (1,); b = not ()",
            "a = not {1:2}; b = not {}",
            "a = not [1, 2]; b = not []",
            "a = not {1, 2}; b = not set()", # set() is a special case because it's handled by ast.literal_eval()
            "a = not 1; b = not 0",
            'a = not "a"; b = not ""',
            'a = not b"a"; b = not b""',
        ):
            mod = self.parse(code)
            assert next(mod.locals["a"][0].infer()).literal_eval() == False
            assert next(mod.locals["b"][0].infer()).literal_eval() == False

    @pytest.mark.xfail
    def test_unary_op_numbers(self) -> None:
        return
        ast_nodes = self.parse(
            """
            +1
            -1 
            ~1 
            +2.0 
            -2.0 
            """
            ).body
        expected = [1, -1, -2, 2.0, -2.0]
        for node, expected_value in zip(ast_nodes, expected):
            inferred = next(node.value.infer())
            self.assertEqual(inferred.value, expected_value)
            self.assertEqual(inferred.literal_eval(), expected_value)

    def _test_const_inferred(self, node: ast.Name, value: Any) -> None:
        inferred = list(node.infer())
        self.assertEqual(len(inferred), 1)
        self.assertIsInstance(inferred[0], ast.Constant)
        self.assertEqual(inferred[0].value, value)

    def test_binary_op_int_add(self) -> None:
        mod = self.parse("a = 1 + 2")
        self._test_const_inferred(mod.locals["a"][0], 3)

    def test_binary_op_int_sub(self) -> None:
        mod = self.parse("a = 1 - 2")
        self._test_const_inferred(mod.locals["a"][0], -1)

    def test_binary_op_float_div(self) -> None:
        mod = self.parse("a = 1 / 2.")
        self._test_const_inferred(mod.locals["a"][0], 1 / 2.0)

    def test_binary_op_str_mul(self) -> None:
        mod = self.parse('a = "*" * 40')
        self._test_const_inferred(mod.locals["a"][0], "*" * 40)

    def test_binary_op_int_bitand(self) -> None:
        mod = self.parse("a = 23&20")
        self._test_const_inferred(mod.locals["a"][0], 23 & 20)

    def test_binary_op_int_bitor(self) -> None:
        mod = self.parse("a = 23|8")
        self._test_const_inferred(mod.locals["a"][0], 23 | 8)

    def test_binary_op_int_bitxor(self) -> None:
        mod = self.parse("a = 23^9")
        self._test_const_inferred(mod.locals["a"][0], 23 ^ 9)

    def test_binary_op_int_shiftright(self) -> None:
        mod = self.parse("a = 23 >>1")
        self._test_const_inferred(mod.locals["a"][0], 23 >> 1)

    def test_binary_op_int_shiftleft(self) -> None:
        mod = self.parse("a = 23 <<1")
        self._test_const_inferred(mod.locals["a"][0], 23 << 1)

    def test_nonregr_multi_referential_addition(self) -> None:
        """Regression test for https://github.com/PyCQA/astroid/issues/483
        Make sure issue where referring to the same variable
        in the same inferred expression caused an uninferable result.
        """
        code = """
        b = 1
        a = b + b
        a
        """
        variable_a = self.parse(code).body[-1]
        self.assertEqual(next(variable_a.infer()).value, 2)

# Not in scope for the moment
# def test_nonregr_layed_dictunpack(self) -> None:
#         """Regression test for https://github.com/PyCQA/astroid/issues/483
#         Make sure multiple dictunpack references are inferable
#         """
#         code = """
#         base = {'data': 0}
#         new = {**base, 'data': 1}
#         new3 = {**base, **new}
#         new3
#         """
#         ass = extract_node(code)
#         self.assertIsInstance(ass.inferred()[0], ast.Dict)

    def test_augassign(self) -> None:
            code = """
                a = 1
                a += 2
                a
            """
            mod = self.parse(code)

            _first_name = mod.body[0].targets[0]
            assert isinstance(_first_name, ast.Name)
            inferred = list(_first_name.infer())

            self.assertEqual(len(inferred), 1)
            self.assertIsInstance(inferred[0], ast.Constant)
            self.assertEqual(inferred[0].value, 1)
            
            # 'a' from the locals
            augassign_name = mod.locals['a'][-1]
            assert augassign_name.lookup('a')[1][0] == _first_name, augassign_name.lookup('a')
            
            inferred = list(augassign_name.infer())
            self.assertEqual(len(inferred), 1)
            self.assertIsInstance(inferred[0], ast.Constant)
            self.assertEqual(inferred[0].value, 3)

            # 'a' expr name load
            _last_name = mod.body[-1].value
            assert isinstance(_last_name, ast.Name)
            inferred = list(_last_name.infer())

            self.assertEqual(len(inferred), 1)
            self.assertIsInstance(inferred[0], ast.Constant)
            self.assertEqual(inferred[0].value, 3)

# Not in scope, this should return the Uninferable result instead.
# TODO: test that.
# def test_list_inference(self) -> None:
#     """#20464"""
#     code = """
#         from unknown import Thing
#         A = []
#         B = []
#         [Thing] + A + B
#     """
#     ast = fromtext(code)
#     inferred = next(ast.body[-1].infer())
#     self.assertIsInstance(inferred, ast.List)
#     self.assertEqual(len(inferred.elts), 1)
#     self.assertIsInstance(inferred.elts[0], ast.Unknown)

    def test_infer_coercion_rules_for_floats_complex(self) -> None:
        ast_nodes = [n.value for n in self.parse(
            """
            1 + 1.0 
            1 * 1.0 
            2 - 1.0 
            2 / 2.0 
            1 + 1j 
            2 * 1j 
            2 - 1j 
            3 / 1j 
            """
            ).body]
        expected_values = [2.0, 1.0, 1.0, 1.0, 1 + 1j, 2j, 2 - 1j, -3j]
        for node, expected in zip(ast_nodes, expected_values):
            inferred = next(node.infer())
            self.assertEqual(inferred.value, expected)

# Not in scope:
# def test_binop_list_with_elts(self) -> None:
#     ast_node = extract_node(
#         """
#     x = [A] * 1
#     [1] + x
#     """
#     )
#     inferred = next(ast_node.infer())
#     self.assertIsInstance(inferred, ast.List)
#     self.assertEqual(len(inferred.elts), 2)
#     self.assertIsInstance(inferred.elts[0], ast.Const)
#     self.assertIsInstance(inferred.elts[1], ast.Unknown)

    def test_binop_same_types(self) -> None:
        ast_nodes = [n.value for n in self.parse(
            """
            1 + 1
            1 - 1
            "a" + "b"
            
            # Not in scope currently
            # class A(object):
            #     def __add__(self, other):
            #         return 42
            # A() + A() #@
            """
            ).body]
        expected_values = [2, 0, "ab"]
        for node, expected in zip(ast_nodes, expected_values):
            inferred = next(node.infer())
            self.assertIsInstance(inferred, ast.Constant)
            self.assertEqual(inferred.value, expected)

# Not in scope:
# def test_starred_in_mapping_inference_issues(self) -> None:
#     code = """
#     {0: 'a', **var} #@
#     {0: 'a', **var, 3: 'd'} #@
#     {0: 'a', **var, 3: 'd', **{**bar, 6: 'g'}} #@
#     """
#     ast = extract_node(code, __name__)
#     for node in ast:
#         with self.assertRaises(InferenceError):
#             next(node.infer())
# def test_starred_in_mapping_literal_non_const_keys_values(self) -> None:
#     code = """
#     a, b, c, d, e, f, g, h, i, j = "ABCDEFGHIJ"
#     var = {c: d, e: f}
#     bar = {i: j}
#     {a: b, **var} #@
#     {a: b, **var, **{g: h, **bar}} #@
#     """
#     ast = extract_node(code, __name__)
#     self.assertInferDict(ast[0], {"A": "B", "C": "D", "E": "F"})
#     self.assertInferDict(ast[1], {"A": "B", "C": "D", "E": "F", "G": "H", "I": "J"})

    def test_starred_in_tuple_literal(self) -> None:
        code = """
        var = (1, 2, 3)
        bar = (5, 6, 7)
        foo = [999, 1000, 1001]
        (0, *var)
        (0, *var, 4)
        (0, *var, 4, *bar)
        (0, *var, 4, *(*bar, 8))
        (0, *var, 4, *(*bar, *foo))
        """
        statements = self.parse(code).body
        self.assertEqual(next(statements[-5].value.infer()).literal_eval(), (0, 1, 2, 3))
        self.assertEqual(next(statements[-4].value.infer()).literal_eval(), (0, 1, 2, 3, 4))
        self.assertEqual(next(statements[-3].value.infer()).literal_eval(), (0, 1, 2, 3, 4, 5, 6, 7))
        self.assertEqual(next(statements[-2].value.infer()).literal_eval(), (0, 1, 2, 3, 4, 5, 6, 7, 8))
        self.assertEqual(next(statements[-1].value.infer()).literal_eval(), (0, 1, 2, 3, 4, 5, 6, 7, 999, 1000, 1001))

    def test_starred_in_list_literal(self) -> None:
        code = """
        var = (1, 2, 3)
        bar = (5, 6, 7)
        foo = [999, 1000, 1001]
        [0, *var] #@
        [0, *var, 4] #@
        [0, *var, 4, *bar] #@
        [0, *var, 4, *[*bar, 8]] #@
        [0, *var, 4, *[*bar, *foo]] #@
        """
        statements = self.parse(code).body
        self.assertEqual(next(statements[-5].value.infer()).literal_eval(), [0, 1, 2, 3])
        self.assertEqual(next(statements[-4].value.infer()).literal_eval(), [0, 1, 2, 3, 4])
        self.assertEqual(next(statements[-3].value.infer()).literal_eval(), [0, 1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(next(statements[-2].value.infer()).literal_eval(), [0, 1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(next(statements[-1].value.infer()).literal_eval(), [0, 1, 2, 3, 4, 5, 6, 7, 999, 1000, 1001])

    def test_starred_in_set_literal(self) -> None:
        code = """
        var = (1, 2, 3)
        bar = (5, 6, 7)
        foo = [999, 1000, 1001]
        {0, *var} #@
        {0, *var, 4} #@
        {0, *var, 4, *bar} #@
        {0, *var, 4, *{*bar, 8}} #@
        {0, *var, 4, *{*bar, *foo}} #@
        """
        statements = self.parse(code).body
        self.assertEqual(next(statements[-5].value.infer()).literal_eval(), {0, 1, 2, 3})
        self.assertEqual(next(statements[-4].value.infer()).literal_eval(), {0, 1, 2, 3, 4})
        self.assertEqual(next(statements[-3].value.infer()).literal_eval(), {0, 1, 2, 3, 4, 5, 6, 7})
        self.assertEqual(next(statements[-2].value.infer()).literal_eval(), {0, 1, 2, 3, 4, 5, 6, 7, 8})
        self.assertEqual(next(statements[-1].value.infer()).literal_eval(), {0, 1, 2, 3, 4, 5, 6, 7, 999, 1000, 1001})

    def test_starred_in_literals_inference_issues(self) -> None:
        # TODO:
        # - This should raises an error because the name 'var' in not defined
        # so we should test if it raises NameInferenceError, no?
        code = """
        {0, *var}
        {0, *var, 4}
        {0, *var, 4, *bar}
        {0, *var, 4, *{*bar, 8}}
        {0, *var, 4, *{*bar, *foo}}
        """
        statements = self.parse(code).body
        for node in statements:
            with self.assertRaises(InferenceError):
                next(node.value.infer())

# Not in scope currently
# def test_starred_in_mapping_literal(self) -> None:
#     code = """
#     var = {1: 'b', 2: 'c'}
#     bar = {4: 'e', 5: 'f'}
#     {0: 'a', **var} #@
#     {0: 'a', **var, 3: 'd'} #@
#     {0: 'a', **var, 3: 'd', **{**bar, 6: 'g'}} #@
#     """
#     ast = extract_node(code, __name__)
#     self.assertInferDict(ast[0], {0: "a", 1: "b", 2: "c"})
#     self.assertInferDict(ast[1], {0: "a", 1: "b", 2: "c", 3: "d"})
#     self.assertInferDict(
#         ast[2], {0: "a", 1: "b", 2: "c", 3: "d", 4: "e", 5: "f", 6: "g"}
#     )

# Nice to have to phase two of astuce
# def test_copy_method_inference(self) -> None:
#         code = """
#         a_dict = {"b": 1, "c": 2}
#         b_dict = a_dict.copy()
#         b_dict #@

#         a_list = [1, 2, 3]
#         b_list = a_list.copy()
#         b_list #@

#         a_set = set([1, 2, 3])
#         b_set = a_set.copy()
#         b_set #@

#         a_frozenset = frozenset([1, 2, 3])
#         b_frozenset = a_frozenset.copy()
#         b_frozenset #@

#         a_unknown = unknown()
#         b_unknown = a_unknown.copy()
#         b_unknown #@
#         """
#         ast = extract_node(code, __name__)
#         self.assertInferDict(ast[0], {"b": 1, "c": 2})
#         self.assertInferList(ast[1], [1, 2, 3])
#         self.assertInferSet(ast[2], [1, 2, 3])
#         self.assertInferFrozenSet(ast[3], [1, 2, 3])

#         inferred_unknown = next(ast[4].infer())
#         assert inferred_unknown == util.Uninferable
