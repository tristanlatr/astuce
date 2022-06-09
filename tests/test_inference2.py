
import ast
from functools import partial
from typing import Any

import pytest

from astuce import nodes, inference, exceptions
from astuce.exceptions import InferenceError
from . import AstuceTestCase, capture_output, fromtext

class Warns(AstuceTestCase):
    def test_some_warnings(self) -> None:
        mod =  self.parse(
            '''
            import b
            class A:...

            [A()]
            []
            [] + [A()]
            [] + b.a + ''
            '''
        )
        # with capture_output() as lines:
        #     list(mod.body[-2].infer())
        # assert lines == []

        with capture_output() as lines:
            mod._report('test')
        assert lines == ['test:???: test'], lines

        with capture_output() as lines:
            assert inference.safe_infer(mod.body[-3]).literal_eval() == []
        assert lines == [], lines

        with capture_output() as lines:
            inference.safe_infer(mod.body[-4]) is None
        assert lines == [], lines

        with capture_output() as lines:
            assert list(mod.body[-1].infer()) == [nodes.Uninferable]          
        assert len(lines) == 4, lines
        # TODO: Is warning like this good?
        # assert all('Uninferable binary operation' in l for l in lines), lines

        with capture_output() as lines:
            assert list(mod.body[-2].infer()) == [nodes.Uninferable]          
        assert len(lines) == 1, lines
        assert "Uninferable operation" in lines[0], lines[0]


class InferAttrTest(AstuceTestCase):

    def test_infer_local(self) -> None:
        
        code = """
            test = ''
            class Pouet:
                __name__ = "pouet"
                test += __name__
            
            class NoName: 
                ann:int
                stuff = Blob()
                
                field = stuff.f('desc')
                test += '_NoName'

                del stuff
                
        
        """
        astroid = self.parse(code)
        
        P = astroid.locals['Pouet'][0]
        inferred = list(inference.infer_attr(P, "__name__"))
        assert len(inferred) == 1
        self.assertEqual(inferred[0].literal_eval(), "pouet")   

        N = astroid.locals['NoName'][0]
        self.assertRaises(exceptions.AttributeInferenceError, lambda:inference.get_attr(N, "notfound"))
        self.assertRaises(exceptions.InferenceError, lambda:list(inference.infer_attr(N, "notfound")))
        self.assertRaises(exceptions.AttributeInferenceError, lambda:inference.get_attr(N, "ann"))
        self.assertRaises(exceptions.InferenceError, lambda:list(inference.infer_attr(N, "ann")))
        self.assertRaises(exceptions.AttributeInferenceError, lambda:inference.get_attr(N, "stuff"))
        self.assertRaises(exceptions.InferenceError, lambda:list(inference.infer_attr(N, "stuff")))

        inferred = list(inference.infer_attr(astroid, "test"))
        assert len(inferred) == 1
        assert inferred[0].literal_eval() == ''
        inferred = list(inference.infer_attr(P, "test"))
        assert len(inferred) == 1
        assert inferred[0].literal_eval() == 'pouet'
        inferred = list(inference.infer_attr(N, "test"))
        assert len(inferred) == 1
        assert inferred[0].literal_eval() == '_NoName'

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

        # pack.f
        assert inference.safe_infer(mod1.body[-1])

        # pack.subpack.E (externaly imported name)
        assert inference.safe_infer(mod1.body[-2]) == None, inference.safe_infer(mod1.body[-2])
        
        # pack.subpack
        with capture_output() as lines:
            assert subpack == inference.get_attr(pack, 'subpack')[0] == inference.get_attr(pack, 'subpack', ignore_locals=True)[0]
            assert inference.safe_infer(mod1.body[-3]) == subpack
        assert lines == [], lines

        # pack.subpack.C
        assert inference.safe_infer(mod1.body[-4]) == inference.get_attr(subpack, 'C')[0], list(inference.infer(mod1.body[-3]))
        # mod2.m, we can't infer calls for now.
        assert list(inference.infer(mod1.body[-5])) == [nodes.Uninferable]
        # mod2.l
        assert inference.safe_infer(mod1.body[-6]) == next(inference.infer_attr(mod2, 'l'))
        # mod2.k
        assert inference.safe_infer(mod1.body[-7]) == next(inference.infer_attr(mod2, 'k'))

        # a.C
        with capture_output() as lines:
            inference.safe_infer(mod1.body[-8]) 
            #== inference.get_attr(subpack, 'C')[0], inference.safe_infer(mod1.body[-8])
        assert lines == [], lines

        # # a
        assert inference.safe_infer(mod1.body[-9]) == subpack
        
        # # pack
        assert inference.safe_infer(mod1.body[-10]) == pack
        


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

        f = list(inference.infer(mod1.body[-1]))
        assert f == [pack.body[-1]], f
        # E
        assert list(inference.infer(mod1.body[-2])) == [nodes.Uninferable]
        # C
        assert list(inference.infer(mod1.body[-3])) == [subpack.body[-1]]
        
        # m
        m = list(inference.infer(mod1.body[-4]))
        # We can't infer calls at this time.
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
            l = inference.safe_infer(mod1.body[-5])
        
        assert lines == []
        assert l.literal_eval() == ('i', 'j')

        # k
        assert inference.safe_infer(mod1.body[-6]).literal_eval() == 'fr'

    def test_import_cycles(self):
        # TODO
        # The test is not implemented but the logic inference
        # should stop and return Uninferable when detecting cycles.
        return NotImplemented

class SequenceInfenceTests(AstuceTestCase):
    
    def test_list_extend(self):
        return NotImplemented
        mod1 = self.parse('''
        from mod2 import l as _l
        l = ['f', 'k']
        l.extend(_l)
        l
        ''', modname='mod1')

        mod2 = self.parse('''
        l = ('i', 'j')
        ''', modname='mod2')

        assert next(mod2.locals['l'][0].infer()).literal_eval() == ('i', 'j')
        
        inferred = list(mod1.body[-1].value.infer())
        assert len(inferred) == 1
        assert inferred[0].literal_eval() == ['f', 'k', 'i', 'j']

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
        a.test
        """
        ).body[-1]
        inferred = next(node.infer())
        assert isinstance(inferred, nodes.Method)
