
import ast
from functools import partial
from typing import Any

from astuce import nodes
from astuce.exceptions import InferenceError
from . import AstuceTestCase


class SequenceInfenceTests(AstuceTestCase):
    
    def test_list_extend(self):
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
