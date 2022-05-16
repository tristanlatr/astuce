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
        assert list(mod.locals) == ['path', 'lol']
        
        assert len(mod.locals['path']) == 2
        
        # assert that the 'from os import path' statement is filtered.
        assert mod.lookup('path')[1] == [mod.body[1]]
