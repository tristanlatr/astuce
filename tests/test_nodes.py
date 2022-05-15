# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt


import ast

import pytest

from astuce import nodes, _typing
from . import AstuceTestCase, require_version

class NodesTest(AstuceTestCase):

    CODE = """
        from typing import List
        
        if 0:
            print()
            var_maybe_unbound = 1

        if True:
            print()
            var_always_set_in_exclusive_bracnhes = 1
        else:
            pass
            var_always_set_in_exclusive_bracnhes = 2

        if "":
            print()
            var_unreachable = 1
        elif []:
            raise
            var_unreachable = 2

        if 1:
            print()
            var_always_set = 3
        elif True:
            print()
            var_always_set = 4
        elif func():
            pass
            var_always_set = 5
        else:
            raise

        def func(x=1) -> int:
            return 4*x
    """

    def test_if_elif_else_node(self) -> None:
        """test transformation for If node"""
        mod = self.parse(self.CODE, 'test')
        
        self.assertEqual(len(mod.body), 6)
        for stmt in mod.body:
            # first and last statements are not if blocks
            if stmt not in [mod.body[0], mod.body[-1]]:
                self.assertIsInstance(stmt, ast.If)
        self.assertFalse(mod.body[1].orelse)  # simple If
        self.assertIsInstance(mod.body[2].orelse[0], ast.Pass)  # If / else
        self.assertIsInstance(mod.body[3].orelse[0], ast.If)  # If / elif
        self.assertIsInstance(mod.body[4].orelse[0].orelse[0], ast.If)
    
    def test_lookup(self) -> None:
        """test transformation for If node"""
        mod = self.parse(self.CODE, 'test')
        
        assert mod.lookup('List') == (mod, [mod.body[0]])
        
        assert mod.lookup('var_maybe_unbound') == (mod, [mod.body[1].body[1].targets[0]])
        
        assert mod.lookup('var_always_set_in_exclusive_bracnhes') == (mod, [mod.body[2].body[1].targets[0], 
                                                       mod.body[2].orelse[1].targets[0]])
        
        assert mod.lookup('var_unreachable') == (mod, [mod.body[3].body[1].targets[0], 
                                                       mod.body[3].orelse[0].body[1].targets[0]])

        assert mod.lookup('var_always_set') == (mod, [mod.body[4].body[1].targets[0], 
                                                       mod.body[4].orelse[0].body[1].targets[0],
                                                       mod.body[4].orelse[0].orelse[0].body[1].targets[0]],)


    def test_lineno(self) -> None:

        mod = self.parse(self.CODE, 'test')
        self.assertEqual(mod.lineno, 0)
        self.assertEqual(mod.body[0].lineno, 2)
        self.assertEqual(mod.body[1].lineno, 4)
        self.assertEqual(mod.body[2].lineno, 8)
        self.assertEqual(mod.body[2].orelse[0].lineno, 12)

    # @staticmethod
    # @pytest.mark.filterwarnings("ignore:.*is_sys_guard:DeprecationWarning")
    # def test_if_sys_guard() -> None:
    #     code = builder.extract_node(
    #         """
    #     import sys
    #     if sys.version_info > (3, 8):  #@
    #         pass

    #     if sys.version_info[:2] > (3, 8):  #@
    #         pass

    #     if sys.some_other_function > (3, 8):  #@
    #         pass
    #     """
    #     )
    #     assert isinstance(code, list) and len(code) == 3

    #     assert isinstance(code[0], nodes.If)
    #     assert code[0].is_sys_guard() is True
    #     assert isinstance(code[1], nodes.If)
    #     assert code[1].is_sys_guard() is True

    #     assert isinstance(code[2], nodes.If)
    #     assert code[2].is_sys_guard() is False

    # @staticmethod
    # @pytest.mark.filterwarnings("ignore:.*is_typing_guard:DeprecationWarning")
    # def test_if_typing_guard() -> None:
    #     code = builder.extract_node(
    #         """
    #     import typing
    #     import typing as t
    #     from typing import TYPE_CHECKING

    #     if typing.TYPE_CHECKING:  #@
    #         pass

    #     if t.TYPE_CHECKING:  #@
    #         pass

    #     if TYPE_CHECKING:  #@
    #         pass

    #     if typing.SOME_OTHER_CONST:  #@
    #         pass
    #     """
    #     )
    #     assert isinstance(code, list) and len(code) == 4

    #     assert isinstance(code[0], nodes.If)
    #     assert code[0].is_typing_guard() is True
    #     assert isinstance(code[1], nodes.If)
    #     assert code[1].is_typing_guard() is True
    #     assert isinstance(code[2], nodes.If)
    #     assert code[2].is_typing_guard() is True

    #     assert isinstance(code[3], nodes.If)
    #     assert code[3].is_typing_guard() is False

class TryExceptNodeTest(AstuceTestCase):
    CODE = """
        try:
            print ('pouet')
        except IOError:
            pass
        except UnicodeError:
            print()
        else:
            print()
    """

    def test_lineno(self) -> None:
        mod = self.parse(self.CODE)
        self.assertEqual(mod.body[0].lineno, 2)
        self.assertEqual(mod.body[0].body[0].lineno, 3)
        
        self.assertEqual(mod.body[0].handlers[0].lineno, 4)
        self.assertEqual(mod.body[0].handlers[0].body[0].lineno,  5)
        
        self.assertEqual(mod.body[0].handlers[1].lineno, 6)
        self.assertEqual(mod.body[0].handlers[1].body[0].lineno,  7)
        self.assertEqual(mod.body[0].orelse[0].lineno, 9)



# class TryFinallyNodeTest(AstuceTestCase):
#     CODE = """
#         try:
#             print ('pouet')
#         finally:
#             print ('pouet')
#     """

#     def test_lineno(self) -> None:
#         mod = self.parse(self.CODE)
#         self.assertEqual(mod.body[0].lineno, 2)
#         self.assertEqual(mod.body[0].lineno, 4)
#         self.assertEqual(mod.body[0].lineno, 5)


# class TryExceptFinallyNodeTest(AstuceTestCase):
#     CODE = """
#         try:
#             print('pouet')
#         except Exception:
#             print ('oops')
#         finally:
#             print ('pouet')
#     """

#     def test_lineno(self) -> None:
#         mod = self.parse(self.CODE)
#         self.assertEqual(mod.body[0].lineno, 2)
#         self.assertEqual(mod.body[0].lineno, 3)
#         self.assertEqual(mod.body[0].lineno, 4)
#         self.assertEqual(mod.body[0].lineno, 5)
#         self.assertEqual(mod.body[0].lineno, 6)
#         self.assertEqual(mod.body[0].lineno, 7)

@require_version((3,8))
class TestNamedExprNode(AstuceTestCase):
    """Tests for the NamedExpr node"""
    CODE = """
            def func(var_1):
                pass

            def func_two(var_2, var_2 = (named_expr_1 := "walrus")):
                pass

            class MyBaseClass:
                pass

            class MyInheritedClass(MyBaseClass, var_3=(named_expr_2 := "walrus")):
                pass

            VAR = lambda y = (named_expr_3 := "walrus"): print(y)

            def func_with_lambda(
                var_5 = (
                    named_expr_4 := lambda y = (named_expr_5 := "walrus"): y
                    )
                ):
                pass

            COMPREHENSION = [y for i in (1, 2) if (y := i ** 2)]
        """
    def test_frame(self) -> None:
        """Test if the frame of NamedExpr is correctly set for certain types
        of parent nodes.
        """
        module = self.parse(self.CODE)
        function = module.body[0]
        assert isinstance(function, ast.FunctionDef)
        function_two = module.body[1]
        assert isinstance(function_two, ast.FunctionDef)
        inherited_class = module.body[3]
        assert isinstance(inherited_class, ast.ClassDef)
        lambda_assignment = module.body[4].value
        assert isinstance(lambda_assignment, ast.Lambda)
        lambda_named_expr = module.body[5].args.defaults[0]
        assert isinstance(lambda_named_expr, ast.NamedExpr)

        assert function.args.frame == function

        
        assert function_two.args.args[0].frame == function_two
        assert function_two.args.args[1].frame == function_two
        assert function_two.args.defaults[0].frame == module

        assert inherited_class.keywords[0].frame == inherited_class
        assert inherited_class.keywords[0].value.frame == module
        
        assert lambda_assignment.args.args[0].frame == lambda_assignment
        assert lambda_assignment.args.defaults[0].frame == module
        
        assert lambda_named_expr.value.args.defaults[0].frame == module

        comprehension = module.body[6].value
        assert comprehension.generators[0].ifs[0].frame == module

    def test_scope(self) -> None:
        """Test if the scope of NamedExpr is correctly set for certain types
        of parent nodes.
        """
        module = self.parse(self.CODE)
        function = module.body[0]
        assert isinstance(function, ast.FunctionDef)
        function_two = module.body[1]
        assert isinstance(function_two, ast.FunctionDef)
        inherited_class = module.body[3]
        assert isinstance(inherited_class, ast.ClassDef)
        lambda_assignment = module.body[4].value
        assert isinstance(lambda_assignment, ast.Lambda)
        lambda_named_expr = module.body[5].args.defaults[0]
        assert isinstance(lambda_named_expr, ast.NamedExpr)
        comprehension = module.body[6].value
        assert isinstance(comprehension, ast.ListComp)

        assert function.args.scope == function

        assert function_two.args.args[0].scope == function_two
        assert function_two.args.args[1].scope == function_two
        assert function_two.args.defaults[0].scope == module

        assert inherited_class.keywords[0].scope == inherited_class
        assert inherited_class.keywords[0].value.scope == module

        assert lambda_assignment.args.args[0].scope == lambda_assignment
        assert lambda_assignment.args.defaults[0].scope

        lambda_named_expr = module.body[5].args.defaults[0]
        assert lambda_named_expr.value.args.defaults[0].scope == module

        assert comprehension.generators[0].ifs[0].scope == module
