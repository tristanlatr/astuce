import ast
import functools
from typing import List

from astuce import exceptions, inference, nodes
from astuce._filter_statements import are_exclusive, filter_stmts
from .test_nodes import CODE_IF_BRANCHES_STATEMENTS
from . import AstuceTestCase, require_version, get_load_names
from astuce._typing import ASTNode as ASTNodeT

class LookupTest(AstuceTestCase):
    def test_lookup(self) -> None:

        mod = self.parse(CODE_IF_BRANCHES_STATEMENTS)
        
        assert mod.lookup('List') == (mod, [mod.body[0].names[0]])
        
        assert mod.lookup('var_maybe_unbound') == (mod, [mod.body[1].body[1].targets[0]])
        
        assert mod.lookup('var_always_set_in_exclusive_bracnhes') == (mod, [mod.body[2].body[1].targets[0], 
                                                       mod.body[2].orelse[1].targets[0]])
        
        assert mod.lookup('var_unreachable') == (mod, [mod.body[3].body[1].targets[0], 
                                                       mod.body[3].orelse[0].body[1].targets[0]])

        assert mod.lookup('var_always_set') == (mod, [mod.body[4].body[1].targets[0], 
                                                       mod.body[4].orelse[0].body[1].targets[0],
                                                       mod.body[4].orelse[0].orelse[0].body[1].targets[0]],)

    def test_lookup_class(self) -> None:

        mod = self.parse('class lol(int):...')
        assert list(mod.locals) == ['lol']
        assert mod.lookup('lol') == (mod, [mod.body[0]])

    def test_filter_statement_simple(self) -> None:
    
        mod = self.parse('''
            from os import path
            class path:...
        ''')
        assert list(mod.locals) == ['path']
        
        assert len(mod.locals['path']) == 2
        
        # assert that the 'from os import path' statement is filtered.
        assert mod.lookup('path')[1] == [mod.body[1]]

    def test_annassigned_stmts(self):
        # assert that an empty annassign node name can't be resolved and returns Uninferable.
        mod = self.parse("""
        a: str = "abc"
        b: str
        """)
        annassign_stmts = mod.body[0], mod.body[1]
        simple_annassign_node = annassign_stmts[0].target
        empty_annassign_node = annassign_stmts[1].target

        assert simple_annassign_node == mod.lookup('a')[1][0], mod.lookup('a')[1]
        
        simple_inferred = list(simple_annassign_node.infer())
        
        self.assertEqual(1, len(simple_inferred))
        self.assertIsInstance(simple_inferred[0], ast.Constant)
        self.assertEqual(simple_inferred[0].value, "abc")

        empty_annassign_inferred = list(empty_annassign_node.infer())

        self.assertEqual(1, len(empty_annassign_inferred))
        self.assertIs(empty_annassign_inferred[0], nodes.Uninferable)


class LookupTest2(AstuceTestCase):
    # def setUp(self) -> None:
    #     super().setUp()
    #     self.module = resources.build_file("data/module.py", "data.module")
    #     self.module2 = resources.build_file("data/module2.py", "data.module2")
    #     self.nonregr = resources.build_file("data/nonregr.py", "data.nonregr")

    def test_limit(self) -> None:
        code = """
            l = [a
                 for a,b in list]
            a = 1
            b = a
            a = None
            def func():
                c = 1
        """
        mod = self.parse(code)
        # a & b
        a = next(nodes.nodes_of_class(mod, ast.Name, 
            predicate= lambda n: not nodes.is_assign_name(n)))
        self.assertEqual(a.lineno, 2)
        self.assertEqual(len(mod.lookup("b")[1]), 1)
        self.assertEqual(len(mod.lookup("a")[1]), 1)
        
        b = mod.locals["b"][0]
        stmts = a.lookup("a")[1]
        self.assertEqual(len(stmts), 1)
        self.assertEqual(b.lineno, 5)
        b_infer = b.infer()
        b_value = next(b_infer)
        self.assertEqual(b_value.value, 1)
        
        # c
        self.assertRaises(StopIteration, functools.partial(next, b_infer))
        func = mod.locals["func"][0]
        self.assertEqual(len(func.lookup("c")[1]), 1)

    # Not in scope for the moment
    # def test_module(self) -> None:
    #     astroid = self.parse("pass")
    #     # built-in objects
    #     none = next(astroid.ilookup("None"))
    #     self.assertIsNone(none.value)
    #     obj = next(astroid.ilookup("object"))
    #     self.assertIsInstance(obj, nodes.ClassDef)
    #     self.assertEqual(obj.name, "object")
    #     self.assertRaises(
    #         InferenceError, functools.partial(next, astroid.ilookup("YOAA"))
    #     )

    #     # XXX
    #     self.assertEqual(len(list(self.nonregr.ilookup("enumerate"))), 2)

    def test_class_ancestor_name(self) -> None:
        code = """
            class A:
                pass
            class A(A):
                pass
        """
        astroid = self.parse(code, __name__)
        cls1 = astroid.locals["A"][0]
        cls2 = astroid.locals["A"][1]
        name = next(nodes.nodes_of_class(cls2, ast.Name, lambda n: not nodes.is_assign_name(n)))
        
        self.assertEqual(next(name.infer()), cls1)

    ### backport those test to inline code
    # def test_method(self) -> None:
    #     method = self.module["YOUPI"]["method"]
    #     my_dict = next(method.ilookup("MY_DICT"))
    #     self.assertTrue(isinstance(my_dict, nodes.Dict), my_dict)
    #     none = next(method.ilookup("None"))
    #     self.assertIsNone(none.value)
    #     self.assertRaises(
    #         InferenceError, functools.partial(next, method.ilookup("YOAA"))
    #     )

    # def test_function_argument_with_default(self) -> None:
    #     make_class = self.module2["make_class"]
    #     base = next(make_class.ilookup("base"))
    #     self.assertTrue(isinstance(base, nodes.ClassDef), base.__class__)
    #     self.assertEqual(base.name, "YO")
    #     self.assertEqual(base.root().name, "data.module")

    # def test_class(self) -> None:
    #     klass = self.module["YOUPI"]
    #     my_dict = next(klass.ilookup("MY_DICT"))
    #     self.assertIsInstance(my_dict, nodes.Dict)
    #     none = next(klass.ilookup("None"))
    #     self.assertIsNone(none.value)
    #     obj = next(klass.ilookup("object"))
    #     self.assertIsInstance(obj, nodes.ClassDef)
    #     self.assertEqual(obj.name, "object")
    #     self.assertRaises(
    #         InferenceError, functools.partial(next, klass.ilookup("YOAA"))
    #     )

    # def test_inner_classes(self) -> None:
    #     ddd = list(self.nonregr["Ccc"].ilookup("Ddd"))
    #     self.assertEqual(ddd[0].name, "Ddd")

    def test_loopvar_hiding(self) -> None:
        astroid = self.parse(
            """
            x = 10
            for x in range(5):
                print (x)
            if x > 0:
                print ('#' * x)
            """)
        xnames = get_load_names(astroid, "x")
        # inside the loop, only one possible assignment
        self.assertEqual(len(xnames[0].lookup("x")[1]), 1)
        # outside the loop, two possible assignments
        self.assertEqual(len(xnames[1].lookup("x")[1]), 2)
        self.assertEqual(len(xnames[2].lookup("x")[1]), 2)

    def test_list_comps(self) -> None:
        astroid = self.parse(
            """
            print ([ i for i in range(10) ])
            print ([ i for i in range(10) ])
            print ( list( i for i in range(10) ) )
            """)
        xnames = get_load_names(astroid, "i")
        self.assertEqual(len(xnames[0].lookup("i")[1]), 1)
        self.assertEqual(xnames[0].lookup("i")[1][0].lineno, 2)
        self.assertEqual(len(xnames[1].lookup("i")[1]), 1)
        self.assertEqual(xnames[1].lookup("i")[1][0].lineno, 3)
        self.assertEqual(len(xnames[2].lookup("i")[1]), 1)
        self.assertEqual(xnames[2].lookup("i")[1][0].lineno, 4)

    def test_list_comp_target(self) -> None:
        """test the list comprehension target"""
        astroid = self.parse(
            """
            ten = [ var for var in range(10) ]
            var
            """)
        var = astroid.body[1].value
        self.assertRaises(exceptions.NameInferenceError, lambda:list(var.infer()))

    def test_dict_comps(self) -> None:
        astroid = self.parse(
            """
            print ({ i: j for i in range(10) for j in range(10) })
            print ({ i: j for i in range(10) for j in range(10) })
            """)
        xnames = get_load_names(astroid, "i")
        self.assertEqual(len(xnames[0].lookup("i")[1]), 1)
        self.assertEqual(xnames[0].lookup("i")[1][0].lineno, 2)
        self.assertEqual(len(xnames[1].lookup("i")[1]), 1)
        self.assertEqual(xnames[1].lookup("i")[1][0].lineno, 3)

        xnames = get_load_names(astroid, "j")
        self.assertEqual(len(xnames[0].lookup("i")[1]), 1)
        self.assertEqual(xnames[0].lookup("i")[1][0].lineno, 2)
        self.assertEqual(len(xnames[1].lookup("i")[1]), 1)
        self.assertEqual(xnames[1].lookup("i")[1][0].lineno, 3)

    def test_set_comps(self) -> None:
        astroid = self.parse(
            """
            print ({ i for i in range(10) })
            print ({ i for i in range(10) })
            """)
        xnames = get_load_names(astroid, "i")
        self.assertEqual(len(xnames[0].lookup("i")[1]), 1)
        self.assertEqual(xnames[0].lookup("i")[1][0].lineno, 2)
        self.assertEqual(len(xnames[1].lookup("i")[1]), 1)
        self.assertEqual(xnames[1].lookup("i")[1][0].lineno, 3)

    def test_set_comp_closure(self) -> None:
        astroid = self.parse(
            """
            ten = { var for var in range(10) }
            var
            """)
        var = astroid.body[1].value
        self.assertRaises(exceptions.NameInferenceError, lambda:list(var.infer()))

    def test_list_comp_nested(self) -> None:
        astroid = self.parse(
            """
            x = [[i + j for j in range(20)]
                 for i in range(10)]
            """)
        xnames = get_load_names(astroid, "i")
        self.assertEqual(len(xnames[0].lookup("i")[1]), 1)
        self.assertEqual(xnames[0].lookup("i")[1][0].lineno, 3)

    def test_dict_comp_nested(self) -> None:
        astroid = self.parse(
            """
            x = {i: {i: j for j in range(20)}
                 for i in range(10)}
            x3 = [{i + j for j in range(20)}  # Can't do nested sets
                  for i in range(10)]
        """)
        xnames = get_load_names(astroid, "i")
        self.assertEqual(len(xnames[0].lookup("i")[1]), 1)
        self.assertEqual(xnames[0].lookup("i")[1][0].lineno, 3)
        self.assertEqual(len(xnames[1].lookup("i")[1]), 1)
        self.assertEqual(xnames[1].lookup("i")[1][0].lineno, 3)

    def test_set_comp_nested(self) -> None:
        astroid = self.parse(
            """
            x = [{i + j for j in range(20)}  # Can't do nested sets
                 for i in range(10)]
        """)
        xnames = get_load_names(astroid, "i")
        self.assertEqual(len(xnames[0].lookup("i")[1]), 1)
        self.assertEqual(xnames[0].lookup("i")[1][0].lineno, 3)

    def test_lambda_nested(self) -> None:
        astroid = self.parse(
            """
            f = lambda x: (
                    lambda y: x + y)
        """
        )
        xnames = get_load_names(astroid, "x")
        self.assertEqual(len(xnames[0].lookup("x")[1]), 1)
        self.assertEqual(xnames[0].lookup("x")[1][0].lineno, 2)

    def test_function_nested(self) -> None:
        astroid = self.parse(
            """
            def f1(x):
                def f2(y):
                    return x + y
                return f2
        """
        )
        xnames = get_load_names(astroid, "x")
        self.assertEqual(len(xnames[0].lookup("x")[1]), 1)
        self.assertEqual(xnames[0].lookup("x")[1][0].lineno, 2)

    def test_class_variables(self) -> None:
        # Class variables are NOT available within nested scopes.
        astroid = self.parse(
            """
            class A:
                a = 10
                def f1(self):
                    return a  # a is not defined
                f2 = lambda: a  # a is not defined
                b = [a for _ in range(10)]  # a is not defined
                class _Inner:
                    inner_a = a + 1
            """
        )
        names = get_load_names(astroid, "a")
        self.assertEqual(len(names), 4)
        for name in names:
            self.assertRaises(exceptions.NameInferenceError, lambda:list(name.infer()))

    def test_class_in_function(self) -> None:
        # Function variables are available within classes, including methods
        astroid = self.parse(
            """
            def f():
                x = 10
                class A:
                    a = x
                    def f1(self):
                        return x
                    f2 = lambda: x
                    b = [x for _ in range(10)]
                    class _Inner:
                        inner_a = x + 1
        """
        )
        names = get_load_names(astroid, "x")
        self.assertEqual(len(names), 5)
        for name in names:
            self.assertEqual(len(name.lookup("x")[1]), 1, repr(name))
            self.assertEqual(name.lookup("x")[1][0].lineno, 3, repr(name))

    # Not in the scope currently.
    # def test_generator_attributes(self) -> None:
    #     tree = self.parse(
    #         """
    #         def count():
    #             "test"
    #             yield 0
    #         iterer = count()
    #         num = iterer.next()
    #     """
    #     )
    #     next_node = tree.body[2].value.func
    #     gener = list(next_node.value.infer())[0]
    #     self.assertIsInstance(gener.getattr("__next__")[0], nodes.FunctionDef)
    #     self.assertIsInstance(gener.getattr("send")[0], nodes.FunctionDef)
    #     self.assertIsInstance(gener.getattr("throw")[0], nodes.FunctionDef)
    #     self.assertIsInstance(gener.getattr("close")[0], nodes.FunctionDef)

    # Not in scope right now.
    # def test_function_module_special(self) -> None:
    #     astroid = self.parse(
    #         '''
    #     def initialize(linter):
    #         """initialize linter with checkers in this package """
    #         package_load(linter, __path__[0])
    #     ''',
    #         "data.__init__",
    #     )
    #     path = [n for n in astroid.nodes_of_class(nodes.Name) if n.name == "__path__"][
    #         0
    #     ]
    #     self.assertEqual(len(path.lookup("__path__")[1]), 1)

    # def test_builtin_lookup(self) -> None:
    #     self.assertEqual(nodes.builtin_lookup("__dict__")[1], ())
    #     intstmts = nodes.builtin_lookup("int")[1]
    #     self.assertEqual(len(intstmts), 1)
    #     self.assertIsInstance(intstmts[0], nodes.ClassDef)
    #     self.assertEqual(intstmts[0].name, "int")
    #     # pylint: disable=no-member
    #     self.assertIs(intstmts[0], nodes.const_factory(1)._proxied)

    def test_decorator_arguments_lookup(self) -> None:
        code = """
            def decorator(value):
                def wrapper(function):
                    return function
                return wrapper
            class foo:
                member = 10  #@
                @decorator(member)
                def test(self):
                    pass
        """

        member = self.parse(code).locals['foo'][0].locals['member'][0]
        it = member.infer()
        obj = next(it)
        self.assertIsInstance(obj, ast.Constant)
        self.assertEqual(obj.value, 10)
        self.assertRaises(StopIteration, functools.partial(next, it))

    def test_inner_decorator_member_lookup(self) -> None:
        code = """
            def decorator(bla):
                'not this one'
            class FileA:
                def decorator(bla):
                    return bla
                @decorator
                def funcA():
                    return 4
        """
        mod = self.parse(code, __name__)
        decname = mod.locals['FileA'][0].locals['funcA'][0].decorator_list[0]
        self.assertIsInstance(decname, ast.Name)
        it = decname.infer()
        obj = next(it)
        self.assertIsInstance(obj, ast.FunctionDef)
        self.assertRaises(StopIteration, functools.partial(next, it))
        assert isinstance(obj.body[0], ast.Return)

    def test_static_method_lookup(self) -> None:
        code = """
            class FileA:
                @staticmethod
                def funcA():
                    return 4
            class Test:
                FileA = [1,2,3]
                def __init__(self):
                    print (FileA.funcA())
        """
        astroid = self.parse(code, __name__)
        _,it = astroid.locals["Test"][0].locals["__init__"][0].lookup("FileA")
        assert len(it)==1
        obj = it[0]
        self.assertIsInstance(obj, ast.ClassDef)

    def test_global_delete(self) -> None:
        code = """
            def run2():
                f = Frobble()
            class Frobble:
                pass
            Frobble.mumble = True
            del Frobble
            def run1():
                f = Frobble()
        """
        astroid = self.parse(code, __name__)
        stmts = astroid.locals["run2"][0].lookup("Frobbel")[1]
        self.assertEqual(len(stmts), 0)
        stmts = astroid.locals["run1"][0].lookup("Frobbel")[1]
        self.assertEqual(len(stmts), 0)


class LookupControlFlowTest(AstuceTestCase):
    """Tests for lookup capabilities and control flow"""

    def test_consecutive_assign(self) -> None:
        """When multiple assignment statements are in the same block, only the last one
        is returned.
        """
        code = """
            x = 10
            x = 100
            print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 3)

    def test_assign_after_use(self) -> None:
        """An assignment statement appearing after the variable is not returned."""
        code = """
            print(x)
            x = 10
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 0)

    def test_del_removes_prior(self) -> None:
        """Delete statement removes any prior assignments"""
        code = """
            x = 10
            del x
            print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 0)

    def test_del_no_effect_after(self) -> None:
        """Delete statement doesn't remove future assignments"""
        code = """
            x = 10
            del x
            x = 100
            print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 4)


    def test_if_assign(self) -> None:
        """Assignment in if statement is added to lookup results, but does not replace
        prior assignments.
        """
        code = """
            def f(b):
                x = 10
                if b:
                    x = 100
                print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 2)
        self.assertEqual([stmt.lineno for stmt in stmts], [3, 5])

    def test_if_assigns_same_branch(self) -> None:
        """When if branch has multiple assignment statements, only the last one
        is added.
        """
        code = """
            def f(b):
                x = 10
                if b:
                    x = 100
                    x = 1000
                print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 2)
        self.assertCountEqual([stmt.lineno for stmt in stmts], [3, 6])

    def test_if_assigns_different_branch(self) -> None:
        """When different branches have assignment statements, the last one
        in each branch is added.
        """
        code = """
            def f(b):
                x = 10
                if b == 1:
                    x = 100
                    x = 1000
                elif b == 2:
                    x = 3
                elif b == 3:
                    x = 4
                print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 4)
        self.assertEqual([stmt.lineno for stmt in stmts], [3, 6, 8, 10])

    def test_assign_exclusive(self) -> None:
        """When the variable appears inside a branch of an if statement,
        no assignment statements from other branches are returned.
        """
        code = """
            def f(b):
                x = 10
                if b == 1:
                    x = 100
                    x = 1000
                elif b == 2:
                    x = 3
                elif b == 3:
                    x = 4
                else:
                    print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 3)

    def test_assign_not_exclusive(self) -> None:
        """When the variable appears inside a branch of an if statement,
        only the last assignment statement in the same branch is returned.
        """
        code = """
            def f(b):
                x = 10
                if b == 1:
                    x = 100
                    x = 1000
                elif b == 2:
                    x = 3
                elif b == 3:
                    x = 4
                    print(x)
                else:
                    x = 5
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 10)

    def test_if_else(self) -> None:
        """When an assignment statement appears in both an if and else branch, both
        are added. This does NOT replace an assignment statement appearing before the
        if statement. (See issue #213)
        """
        code = """
            def f(b):
                x = 10
                if b:
                    x = 100
                else:
                    x = 1000
                print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 3)
        self.assertCountEqual([stmt.lineno for stmt in stmts], [3, 5, 7])

    def test_if_variable_in_condition_1(self) -> None:
        """Test lookup works correctly when a variable appears in an if condition."""
        code = """
            x = 10
            if x > 10:
                print('a')
            elif x > 0:
                print('b')
        """
        astroid = self.parse(code)
        x_name1, x_name2 = get_load_names(astroid, "x")

        _, stmts1 = x_name1.lookup("x")
        self.assertEqual(len(stmts1), 1)
        self.assertEqual(stmts1[0].lineno, 2)

        _, stmts2 = x_name2.lookup("x")
        self.assertEqual(len(stmts2), 1)
        self.assertEqual(stmts2[0].lineno, 2)

    def test_if_variable_in_condition_2(self) -> None:
        """Test lookup works correctly when a variable appears in an if condition,
        and the variable is reassigned in each branch.
        This is based on PyCQA/pylint issue #3711.
        """
        code = """
            x = 10
            if x > 10:
                x = 100
            elif x > 0:
                x = 200
            elif x > -10:
                x = 300
            else:
                x = 400
        """
        astroid = self.parse(code)
        x_names = get_load_names(astroid, "x")

        # All lookups should refer only to the initial x = 10.
        for x_name in x_names:
            _, stmts = x_name.lookup("x")
            self.assertEqual(len(stmts), 1)
            self.assertEqual(stmts[0].lineno, 2)

    def test_del_not_exclusive(self) -> None:
        """A delete statement in an if statement branch removes all previous
        assignment statements when the delete statement is not exclusive with
        the variable (e.g., when the variable is used below the if statement).
        """
        code = """
            def f(b):
                x = 10
                if b == 1:
                    x = 100
                elif b == 2:
                    del x
                elif b == 3:
                    x = 4  # Only this assignment statement is returned
                print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 9)

    def test_del_exclusive(self) -> None:
        """A delete statement in an if statement branch that is exclusive with the
        variable does not remove previous assignment statements.
        """
        code = """
            def f(b):
                x = 10
                if b == 1:
                    x = 100
                elif b == 2:
                    del x
                else:
                    print(x)
        """
        astroid = self.parse(code)
        x_name = get_load_names(astroid, "x")[0]
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 3)

    def test_assign_after_param(self) -> None:
        """When an assignment statement overwrites a function parameter, only the
        assignment is returned, even when the variable and assignment do not have
        the same parent.
        """
        code = """
            def f1(x):
                x = 100
                print(x)
            def f2(x):
                x = 100
                if True:
                    print(x)
        """
        astroid = self.parse(code)
        x_name1, x_name2 = get_load_names(astroid, "x")
        _, stmts1 = x_name1.lookup("x")
        self.assertEqual(len(stmts1), 1)
        self.assertEqual(stmts1[0].lineno, 3)

        _, stmts2 = x_name2.lookup("x")
        self.assertEqual(len(stmts2), 1)
        self.assertEqual(stmts2[0].lineno, 6)

    def test_assign_after_kwonly_param(self) -> None:
        """When an assignment statement overwrites a function keyword-only parameter,
        only the assignment is returned, even when the variable and assignment do
        not have the same parent.
        """
        code = """
            def f1(*, x):
                x = 100
                print(x)
            def f2(*, x):
                x = 100
                if True:
                    print(x)
        """
        astroid = self.parse(code)
        x_name1, x_name2 = get_load_names(astroid, "x")
        _, stmts1 = x_name1.lookup("x")
        self.assertEqual(len(stmts1), 1)
        self.assertEqual(stmts1[0].lineno, 3)

        _, stmts2 = x_name2.lookup("x")
        self.assertEqual(len(stmts2), 1)
        self.assertEqual(stmts2[0].lineno, 6)

    @require_version((3,8))
    def test_assign_after_posonly_param(self):
        """When an assignment statement overwrites a function positional-only parameter,
        only the assignment is returned, even when the variable and assignment do
        not have the same parent.
        """
        code = """
            def f1(x, /):
                x = 100
                print(x)
            def f2(x, /):
                x = 100
                if True:
                    print(x)
        """
        astroid = self.parse(code)
        x_name1, x_name2 = get_load_names(astroid, "x")
        _, stmts1 = x_name1.lookup("x")
        self.assertEqual(len(stmts1), 1)
        self.assertEqual(stmts1[0].lineno, 3)

        _, stmts2 = x_name2.lookup("x")
        self.assertEqual(len(stmts2), 1)
        self.assertEqual(stmts2[0].lineno, 6)

    def test_assign_after_args_param(self) -> None:
        """When an assignment statement overwrites a function parameter, only the
        assignment is returned.
        """
        code = """
            def f(*args, **kwargs):
                args = [100]
                kwargs = {}
                if True:
                    print(args, kwargs)
        """
        astroid = self.parse(code)
        x_name, = get_load_names(astroid, "args")
        _, stmts1 = x_name.lookup("args")
        self.assertEqual(len(stmts1), 1)
        self.assertEqual(stmts1[0].lineno, 3)

        x_name, = get_load_names(astroid, "kwargs")
        _, stmts2 = x_name.lookup("kwargs")
        self.assertEqual(len(stmts2), 1)
        self.assertEqual(stmts2[0].lineno, 4)

    # Variables defined in expect blocks not in scope right now, but maybe soon.
    # def test_except_var_in_block(self) -> None:
    #     """When the variable bound to an exception in an except clause, it is returned
    #     when that variable is used inside the except block.
    #     """
    #     code = """
    #         try:
    #             1 / 0
    #         except ZeroDivisionError as e:
    #             print(e)
    #     """
    #     astroid = self.parse(code)
    #     x_name, = get_load_names(astroid, "e")
    #     _, stmts = x_name.lookup("e")
    #     self.assertEqual(len(stmts), 1)
    #     self.assertEqual(stmts[0].lineno, 4)

    # def test_except_var_in_block_overwrites(self) -> None:
    #     """When the variable bound to an exception in an except clause, it is returned
    #     when that variable is used inside the except block, and replaces any previous
    #     assignments.
    #     """
    #     code = """
    #         e = 0
    #         try:
    #             1 / 0
    #         except ZeroDivisionError as e:
    #             print(e)
    #     """
    #     astroid = builder.parse(code)
    #     x_name = [n for n in astroid.nodes_of_class(nodes.Name) if n.name == "e"][0]
    #     _, stmts = x_name.lookup("e")
    #     self.assertEqual(len(stmts), 1)
    #     self.assertEqual(stmts[0].lineno, 5)

    # def test_except_var_in_multiple_blocks(self) -> None:
    #     """When multiple variables with the same name are bound to an exception
    #     in an except clause, and the variable is used inside the except block,
    #     only the assignment from the corresponding except clause is returned.
    #     """
    #     code = """
    #         e = 0
    #         try:
    #             1 / 0
    #         except ZeroDivisionError as e:
    #             print(e)
    #         except NameError as e:
    #             print(e)
    #     """
    #     astroid = builder.parse(code)
    #     x_names = [n for n in astroid.nodes_of_class(nodes.Name) if n.name == "e"]

    #     _, stmts1 = x_names[0].lookup("e")
    #     self.assertEqual(len(stmts1), 1)
    #     self.assertEqual(stmts1[0].lineno, 5)

    #     _, stmts2 = x_names[1].lookup("e")
    #     self.assertEqual(len(stmts2), 1)
    #     self.assertEqual(stmts2[0].lineno, 7)

    # def test_except_var_after_block_single(self) -> None:
    #     """When the variable bound to an exception in an except clause, it is NOT returned
    #     when that variable is used after the except block.
    #     """
    #     code = """
    #         try:
    #             1 / 0
    #         except NameError as e:
    #             pass
    #         print(e)
    #     """
    #     astroid = builder.parse(code)
    #     x_name = [n for n in astroid.nodes_of_class(nodes.Name) if n.name == "e"][0]
    #     _, stmts = x_name.lookup("e")
    #     self.assertEqual(len(stmts), 0)

    # def test_except_var_after_block_multiple(self) -> None:
    #     """When the variable bound to an exception in multiple except clauses, it is NOT returned
    #     when that variable is used after the except blocks.
    #     """
    #     code = """
    #         try:
    #             1 / 0
    #         except NameError as e:
    #             pass
    #         except ZeroDivisionError as e:
    #             pass
    #         print(e)
    #     """
    #     astroid = builder.parse(code)
    #     x_name = [n for n in astroid.nodes_of_class(nodes.Name) if n.name == "e"][0]
    #     _, stmts = x_name.lookup("e")
    #     self.assertEqual(len(stmts), 0)

    # def test_except_assign_in_block(self) -> None:
    #     """When a variable is assigned in an except block, it is returned
    #     when that variable is used in the except block.
    #     """
    #     code = """
    #         try:
    #             1 / 0
    #         except ZeroDivisionError as e:
    #             x = 10
    #             print(x)
    #     """
    #     astroid = builder.parse(code)
    #     x_name = [n for n in astroid.nodes_of_class(nodes.Name) if n.name == "x"][0]
    #     _, stmts = x_name.lookup("x")
    #     self.assertEqual(len(stmts), 1)
    #     self.assertEqual(stmts[0].lineno, 5)

    def test_except_assign_in_block_multiple(self) -> None:
        """When a variable is assigned in multiple except blocks, and the variable is
        used in one of the blocks, only the assignments in that block are returned.
        """
        code = """
            try:
                1 / 0
            except ZeroDivisionError:
                x = 10
            except NameError:
                x = 100
                print(x)
        """
        astroid = self.parse(code)
        x_name, = get_load_names(astroid, "x")
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 7)

    def test_except_assign_after_block(self) -> None:
        """When a variable is assigned in an except clause, it is returned
        when that variable is used after the except block.
        """
        code = """
            try:
                1 / 0
            except ZeroDivisionError:
                x = 10
            except NameError:
                x = 100
            print(x)
        """
        astroid = self.parse(code)
        x_name, = get_load_names(astroid, "x")
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 2)
        self.assertCountEqual([stmt.lineno for stmt in stmts], [5, 7])

    def test_except_assign_after_block_overwritten(self) -> None:
        """When a variable is assigned in an except clause, it is not returned
        when it is reassigned and used after the except block.
        """
        code = """
            try:
                1 / 0
            except ZeroDivisionError:
                x = 10
            except NameError:
                x = 100
            x = 1000
            print(x)
        """
        astroid = self.parse(code)
        x_name, = get_load_names(astroid, "x")
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 8)
    
    def test_except_assign_after_block_in_class(self) -> None:
        """When a variable is assigned in an except clause, it is returned
        when that variable is used after the except block.
        """
        code = """
        class C:
            try:
                1 / 0
            except ZeroDivisionError:
                x = 10
            except NameError:
                x = 100
            print(x)
        """
        astroid = self.parse(code)
        x_name, = get_load_names(astroid, "x")
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 2)
        self.assertCountEqual([stmt.lineno for stmt in stmts], [6, 8])

    def test_except_assign_after_block_overwritten_in_class(self) -> None:
        """When a variable is assigned in an except clause, it is not returned
        when it is reassigned and used after the except block.
        """
        code = """
        class C:
            try:
                1 / 0
            except ZeroDivisionError:
                x = 10
            except NameError:
                x = 100
            x = 1000
            print(x)
        """
        astroid = self.parse(code)
        x_name, = get_load_names(astroid, "x")
        _, stmts = x_name.lookup("x")
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 9)

# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

class TestAreExclusive(AstuceTestCase):
    def test_not_exclusive(self) -> None:
        module = self.parse(
            """
        x = 10
        for x in range(5):
            print (x)

        if x > 0:
            print ('#' * x)
        """)
        xass1 = module.locals["x"][0]
        assert xass1.lineno == 2
        xnames = get_load_names(module, "x")
        assert len(xnames) == 3
        assert xnames[1].lineno == 6
        self.assertEqual(are_exclusive(xass1, xnames[1]), False)
        self.assertEqual(are_exclusive(xass1, xnames[2]), False)

    def test_if(self) -> None:
        module = self.parse(
            """
        if 1:
            a = 1
            a = 2
        elif 2:
            a = 12
            a = 13
        else:
            a = 3
            a = 4
        """
        )
        a1 = module.locals["a"][0]
        a2 = module.locals["a"][1]
        a3 = module.locals["a"][2]
        a4 = module.locals["a"][3]
        a5 = module.locals["a"][4]
        a6 = module.locals["a"][5]
        self.assertEqual(are_exclusive(a1, a2), False)
        self.assertEqual(are_exclusive(a1, a3), True)
        self.assertEqual(are_exclusive(a1, a5), True)
        self.assertEqual(are_exclusive(a3, a5), True)
        self.assertEqual(are_exclusive(a3, a4), False)
        self.assertEqual(are_exclusive(a5, a6), False)

    def test_try_except(self) -> None:
        return NotImplemented
        module = self.parse(
            """
        try:
            def exclusive_func2():
                "docstring"
        except TypeError:
            def exclusive_func2():
                "docstring"
        except:
            def exclusive_func2():
                "docstring"
        else:
            def exclusive_func2():
                "this one redefine the one defined line 42"
        """
        )
        f1 = module.locals["exclusive_func2"][0]
        f2 = module.locals["exclusive_func2"][1]
        f3 = module.locals["exclusive_func2"][2]
        f4 = module.locals["exclusive_func2"][3]
        self.assertEqual(are_exclusive(f1, f2), True)
        self.assertEqual(are_exclusive(f1, f3), True)
        self.assertEqual(are_exclusive(f1, f4), False)
        self.assertEqual(are_exclusive(f2, f4), True)
        self.assertEqual(are_exclusive(f3, f4), True)
        self.assertEqual(are_exclusive(f3, f2), True)

        self.assertEqual(are_exclusive(f2, f1), True)
        self.assertEqual(are_exclusive(f4, f1), False)
        self.assertEqual(are_exclusive(f4, f2), True)

class TestGetAttr(AstuceTestCase):

    
    def test_except_assign_exclusive_branches_get_attr(self) -> None:
        """When a variable is assigned in exlcusive branches, both are returned
        """
        code = """
            try:
                1 / 0
            except ZeroDivisionError:
                x = 10
            except NameError:
                x = 100
            print(x)
        """
        astroid = self.parse(code)
        stmts = inference.get_attr(astroid, 'x')
        self.assertEqual(len(stmts), 2)
        
        self.assertEqual(stmts[0].lineno, 5)
        self.assertEqual(stmts[1].lineno, 7)
    
    def test_except_assign_after_block_overwritten_get_attr(self) -> None:
        """When a variable is assigned in an except clause, it is not returned
        when it is reassigned and used after the except block.
        """
        code = """
            try:
                1 / 0
            except ZeroDivisionError:
                x = 10
            except NameError:
                x = 100
            x = 1000
            print(x)
        """
        astroid = self.parse(code)
        stmts = inference.get_attr(astroid, 'x')
        self.assertEqual(len(stmts), 1)
        self.assertEqual(stmts[0].lineno, 8)
