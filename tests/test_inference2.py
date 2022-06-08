
import ast
from functools import partial
from typing import Any

import pytest

from astuce import nodes, inference, exceptions
from astuce.exceptions import InferenceError
from . import AstuceTestCase

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
        self.assertRaises(exceptions.AttributeInferenceError, lambda:list(inference.get_attr(N, "notfound")))
        self.assertRaises(exceptions.InferenceError, lambda:list(inference.infer_attr(N, "notfound")))
        self.assertRaises(exceptions.AttributeInferenceError, lambda:list(inference.get_attr(N, "ann")))
        self.assertRaises(exceptions.InferenceError, lambda:list(inference.infer_attr(N, "ann")))
        self.assertRaises(exceptions.AttributeInferenceError, lambda:list(inference.get_attr(N, "stuff")))
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
        return NotImplemented
        pack = self.parse('''
        def f():...
        ''', modname='pack', is_package=True)

        subpack = self.parse('''
        from external import E
        class C: ...
        ''', modname='pack.subpack')

        mod1 = self.parse('''
        import mod2 
        import pack.subpack

        mod2.k
        mod2.l
        mod2.m
        pack.subpack.C
        pack.subpack.E
        pack.f
        
        ''', modname='mod1')

        mod2 = self.parse('''
        k = 'fr'
        l = ('i', 'j')
        m = range(10)
        ''', modname='mod2')

        assert list(inference.recursively_infer(mod1.body[-1])) == []
        assert list(inference.recursively_infer(mod1.body[-2])) == []
        assert list(inference.recursively_infer(mod1.body[-3])) == []
        assert list(inference.recursively_infer(mod1.body[-4])) == []
        assert list(inference.recursively_infer(mod1.body[-5])) == []
        assert list(inference.recursively_infer(mod1.body[-6])) == []


    def test_import_from_simple(self):
        return NotImplemented
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

        assert list(inference.recursively_infer(mod1.body[-1])) == []
        assert list(inference.recursively_infer(mod1.body[-2])) == []
        assert list(inference.recursively_infer(mod1.body[-3])) == []
        assert list(inference.recursively_infer(mod1.body[-4])) == []
        assert list(inference.recursively_infer(mod1.body[-5])) == []
        assert list(inference.recursively_infer(mod1.body[-6])) == []

    def test_import_cycles(self):
        ...

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
