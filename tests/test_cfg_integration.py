
import ast
from functools import partial
from typing import Any

import pytest

from astuce import inference, nodes, cfg
from astuce.exceptions import InferenceError, NameInferenceError
from . import AstuceTestCase, get_exprs, get_load_names
from astuce.parser import _unparse as unparse, Parser


class CFGTests(AstuceTestCase):
   
    def test_get_cfg_from_function(self):
        code = """
            def py36() -> bool:
                if sys.version_info >= (3,6):
                    return True
                else:
                    return False
        """
        astroid = self.parse(code)
        func_cfg = astroid.locals['py36'][0].cfg
        return_True_block = astroid.locals['py36'][0].body[0].body[0].block
        assert isinstance(func_cfg, cfg.CFG)
        assert isinstance(return_True_block, cfg.Block)

    
    def test_get_cfg_from_class(self):
        code = """
            class Program:
                if sys.version_info >= (3,6):
                    supported = True
                else:
                    supported = False
        """
        astroid = self.parse(code)
        func_cfg = astroid.locals['Program'][0].cfg
        supported_True_block = astroid.locals['Program'][0].body[0].body[0].block
        assert isinstance(func_cfg, cfg.CFG)
        assert isinstance(supported_True_block, cfg.Block)
        assert len(supported_True_block.exits)==1
        assert supported_True_block.exits[0].exitcase is None
        assert supported_True_block.predecessors[0].exits[0].exitcase is None


    
    def test_get_block_from_statement(self):
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
        mod_cfg = astroid.cfg
        block_1 = astroid.body[0].body[0].block
        assert isinstance(mod_cfg, cfg.CFG)
        assert isinstance(block_1, cfg.Block)
        assert block_1.id == 2
        assert block_1.get_source() == '#2\n1 / 0\n'
    
    def test_filter_statement_with_cfg(self):
        ...
        code = """
            if True:
                v = True
            else:
                v = False
            
            if False:
                d = False
            else:
                d = True
        """

        astroid = self.parse(code)
        
    