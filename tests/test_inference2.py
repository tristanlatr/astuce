
import ast
from functools import partial
from typing import Any

import pytest

from astuce import nodes, inference, exceptions, _lookup
from astuce.exceptions import InferenceError
from astuce._filter_statements import filter_stmts
from . import AstuceTestCase, capture_output, get_exprs, fromtext, get_load_names

class Warns(AstuceTestCase):
    def test_some_warnings(self) -> None:
        mod =  self.parse(
            '''
            import b
            class A:...

            w = [A()]
            v = []
            i = [] + [A()]
            j = [] + b.a + ''
            '''
        )
        # with capture_output() as lines:
        #     list(mod.body[-2].infer())
        # assert lines == []

        with capture_output() as lines:
            mod._report('test')
        assert lines == ['test:???: test'], lines

        with capture_output() as lines:
            assert ast.literal_eval(inference.safe_infer(mod.locals['v'][0])) == []
        assert lines == [], lines

        with capture_output() as lines:
            inference.safe_infer(mod.locals['w'][0]) is None
        assert lines == ['test:5: Sequence element (0) is not inferable'], lines

        with capture_output() as lines:
            assert list(mod.locals['j'][0].infer()) == [nodes.Uninferable]          
        assert len(lines) == 4, lines
        # TODO: Is warning like this good?
        # assert all('Uninferable binary operation' in l for l in lines), lines

        with capture_output() as lines:
            assert list(mod.locals['i'][0].infer()) == [nodes.Uninferable]          
        assert len(lines) == 2, lines
        assert "Sequence element (0) is not inferable" in lines[0], lines[0]
        assert "Uninferable operation" in lines[1], lines[1]


class InferAttrTest(AstuceTestCase):

    def test_infer_local(self) -> None:
        
        code = """
            test = ''
            class Pouet:
                __name__ = "erased"
                __name__ = "pouet"
                test += __name__
                bob = "pouet"
                print('testing')
                print('testing')
            
            class NoName: 
                ann:int
                stuff = Blob()
                
                field = stuff.f('desc')
                test += '_NoName'

                del stuff
                
        
        """
        astroid = self.parse(code)
        
        P = astroid.locals['Pouet'][0]

        assert len(filter_stmts(P, P.locals['__name__'], P, 0)) == 1
        
        # with inference._tmp_end_body_name(P, '__name__') as _temp:
        #     assert _temp.parent in P.children
        #     assert P.body[-1] == _temp.parent

        #     # assert P.locals['__name__'] == []
            

        #     # assert inference.safe_infer(_temp) == P.locals['__name__'][0], inference.safe_infer(_temp)
        #     # assert _lookup.lookup(_temp, '__name__', 0)[1] != []
        
        P.body[-1].unparse() == "print('testing')"

        assert _lookup.lookup(P.body[-1].value, '__name__', 0)[1] != [], _lookup.lookup(P.body[-1].value, '__name__', 0)
        assert _lookup.lookup(P, '__name__', 0)[1] != [], _lookup.lookup(P, '__name__', 0)
        
        

        inferred = list(inference.infer_attr(P, "bob"))
        # inferred = list(inference.infer_attr(P, "__name__"))
        
        assert len(inferred) == 1
        self.assertEqual(ast.literal_eval(inferred[0]), "pouet")   

        N = astroid.locals['NoName'][0]
        self.assertRaises(exceptions.AttributeInferenceError, lambda:inference.get_attr(N, "notfound"))
        self.assertRaises(exceptions.InferenceError, lambda:list(inference.infer_attr(N, "notfound")))
        self.assertRaises(exceptions.AttributeInferenceError, lambda:inference.get_attr(N, "ann"))
        self.assertRaises(exceptions.InferenceError, lambda:list(inference.infer_attr(N, "ann")))
        self.assertRaises(exceptions.AttributeInferenceError, lambda:inference.get_attr(N, "stuff"))
        self.assertRaises(exceptions.InferenceError, lambda:list(inference.infer_attr(N, "stuff")))

        inferred = list(inference.infer_attr(astroid, "test"))
        assert len(inferred) == 1
        assert ast.literal_eval(inferred[0]) == ''
        inferred = list(inference.infer_attr(P, "test"))
        assert len(inferred) == 1
        assert ast.literal_eval(inferred[0]) == 'pouet'
        inferred = list(inference.infer_attr(N, "test"))
        assert len(inferred) == 1
        assert ast.literal_eval(inferred[0]) == '_NoName'

class ImportsTests(AstuceTestCase):
    def test_import_simple(self):

        pack = self.parse('''
        def f():...
        ''', modname='pack', is_package=True)

        subpack = self.parse('''
        from external import E
        class C: ...
        ''', modname='pack.subpack')

        mod1 = self.parse('''
        import mod2

        # Importing pack.subpack imports pack also, but not if we use an alias
        import pack.subpack
        import pack.subpack as a

        pack
        a
        a.C
        mod2.k
        mod2.l
        mod2.m
        pack.subpack.C
        pack.subpack
        pack.subpack.E
        pack.f
        
        ''', modname='mod1')

        mod2 = self.parse('''
        k = 'fr'
        l = ('i', 'j')
        m = range(10)
        ''', modname='mod2')

        f = list(inference.infer(mod1.locals['pack'][0]))
        assert f == [pack], f
        assert nodes.get_origin_module(mod1.locals['a'][0]) == 'pack.subpack'
        assert nodes.get_origin_module(mod1.locals['pack'][0]) == 'pack'

        filtered_body = get_exprs(mod1.body)

        # pack.f
        assert inference.safe_infer(filtered_body[-1])

        # pack.subpack.E (externaly imported name)
        assert inference.safe_infer(filtered_body[-2]) == None, inference.safe_infer(filtered_body[-2])
        
        # pack.subpack
        with capture_output() as lines:
            assert subpack == inference.get_attr(pack, 'subpack')[0] == inference.get_attr(pack, 'subpack', ignore_locals=True)[0]
            assert inference.safe_infer(filtered_body[-3]) == subpack
        assert lines == [], lines

        # pack.subpack.C
        assert inference.safe_infer(filtered_body[-4]) == inference.get_attr(subpack, 'C')[0], list(inference.infer(filtered_body[-3]))
        # mod2.m, we can't infer calls for now.
        assert list(inference.infer(filtered_body[-5])) == [nodes.Uninferable]
        # mod2.l
        assert inference.safe_infer(filtered_body[-6]) == next(inference.infer_attr(mod2, 'l'))
        # mod2.k
        assert inference.safe_infer(filtered_body[-7]) == next(inference.infer_attr(mod2, 'k'))

        # a.C
        with capture_output() as lines:
            inference.safe_infer(filtered_body[-8]) 
            #== inference.get_attr(subpack, 'C')[0], inference.safe_infer(filtered_body[-8])
        assert lines == [], lines

        # # a
        assert inference.safe_infer(filtered_body[-9]) == subpack
        
        # # pack
        assert inference.safe_infer(filtered_body[-10]) == pack
        


    def test_import_from_simple(self):

        pack = self.parse('''
        from .subpack import C, E
        def f():...
        ''', modname='pack', is_package=True)

        subpack = self.parse('''
        from external import E
        class C: ...
        ''', modname='pack.subpack')

        mod1 = self.parse('''
        from mod2 import _k as k, _l as l, _m as m
        from pack import C, E, f

        k
        l
        m
        C
        E
        f
        
        ''', modname='mod1')

        mod2 = self.parse('''
        _k = 'fr'
        _l = ('i', 'j')
        _m = range(10)
        ''', modname='mod2')

        filtered_body = get_exprs(mod1.body)

        f = list(inference.infer(filtered_body[-1]))
        assert f == [pack.locals['f'][0]], f
        # E
        assert list(inference.infer(filtered_body[-2])) == [nodes.Uninferable]
        # C
        assert list(inference.infer(filtered_body[-3])) == [subpack.locals['C'][0]]
        
        # m
        m = list(inference.infer(filtered_body[-4]))
        # We can't infer calls at this time.
        NotImplemented
        assert m == [nodes.Uninferable], m
        
        # l
        import_alias = mod1.locals['l'][0]
        assert isinstance(import_alias, ast.alias)
        assert nodes.get_full_import_name(import_alias) == 'mod2._l', nodes.get_full_import_name(import_alias)
        assert nodes.get_origin_module(import_alias) == 'mod2', nodes.get_origin_module(import_alias)
        
        with capture_output() as lines:
            inference.safe_infer(import_alias) is not None
        assert lines == []

        with capture_output() as lines:
            l = inference.safe_infer(filtered_body[-5])
        
        assert lines == []
        assert ast.literal_eval(l) == ('i', 'j')

        # k
        assert ast.literal_eval(inference.safe_infer(filtered_body[-6])) == 'fr'

    def test_import_cycles(self):
        # TODO
        # The test is not implemented but the logic inference
        # should stop and return Uninferable when detecting cycles.
        return NotImplemented

class SequenceInfenceTests(AstuceTestCase):
    
    def test_list_augassign(self):

        mod1 = self.parse('''
        from mod2 import __all__ as _l
        __all__ = ['f'] 
        __all__ += ['k']
        __all__ += []
        __all__ += _l
        __all__ += []
        __all__
        ''', modname='mod1')

        mod2 = self.parse('''
        __all__ = ('i', 'j')
        ''', modname='mod2')

        assert ast.literal_eval(next(mod2.locals['__all__'][0].infer())) == ('i', 'j')

        with capture_output() as lines:
            list(inference.infer_attr(mod1, '__all__'))[0]
        assert lines == [], lines
        
        with capture_output() as lines:
            inferred = list(get_load_names(mod1, '__all__')[0].infer())
        assert lines == [], lines

        assert len(inferred) == 1
        assert ast.literal_eval(inferred[0]) == ['f', 'k', 'i', 'j'], ast.literal_eval(inferred[0])

        
    def test_list_extend(self):

        mod1 = self.parse('''
        from mod2 import __all__ as _l
        __all__ = ['f', 'k']
        __all__.extend(_l)
        __all__
        ''', modname='mod1')

        mod2 = self.parse('''
        __all__ = ('i', 'j')
        ''', modname='mod2')

        assert ast.literal_eval(next(mod1.locals['__all__'][0].infer())) == ['f', 'k']
        assert ast.literal_eval(next(mod2.locals['__all__'][0].infer())) == ('i', 'j')

        with capture_output() as lines:
            list(inference.infer_attr(mod1, '__all__'))[0]
        assert lines == [], lines

        filtered_body = get_exprs(mod1.body)

        # with capture_output() as lines:
        #     assert inference.safe_infer(fbody[-2]), list(fbody[-2].infer())
        # assert lines == [], lines

        with capture_output() as lines:
            inferred = list(filtered_body[-1].infer())
        assert lines == [], lines

        assert len(inferred) == 1
        assert ast.literal_eval(inferred[0]) == ['f', 'k', 'i', 'j'], ast.literal_eval(inferred[0])

class MoreInferenceTests(AstuceTestCase):

    def test_is_BoundMethod(self) -> None:
        return NotImplemented

        node = self.parse(
        """
        class A:
            def test(self):
                a = yield
                while True:
                    print(a)
                    yield a
        a = A()
        test = a.test
        """
        )
        inferred = next(node.locals['test'][0].infer())
        assert isinstance(inferred, nodes.Method)
