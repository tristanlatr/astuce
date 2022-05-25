import ast

from astuce import nodes
from .test_nodes import CODE_IF_BRANCHES_STATEMENTS
from . import AstuceTestCase
class LookupTest(AstuceTestCase):
    def test_lookup(self) -> None:

        mod = self.parse(CODE_IF_BRANCHES_STATEMENTS)
        
        assert mod.lookup('List') == (mod, [mod.body[0]])
        
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
        # assert that an empty annassign node name can't be resolved an returns Uninferable.
        mod = self.parse("""
        a: str = "abc"
        b: str
        """)
        annassign_stmts = mod.body[0], mod.body[1]
        simple_annassign_node = annassign_stmts[0].target
        empty_annassign_node = annassign_stmts[1].target

        assert simple_annassign_node == mod.lookup('a')[1]
        
        simple_inferred = list(simple_annassign_node.infer())
        
        self.assertEqual(1, len(simple_inferred))
        self.assertIsInstance(simple_inferred[0], ast.Constant)
        self.assertEqual(simple_inferred[0].value, "abc")

        empty_annassign_inferred = list(empty_annassign_node.infer())

        self.assertEqual(1, len(empty_annassign_inferred))
        self.assertIs(empty_annassign_inferred[0], nodes.Uninferable)
