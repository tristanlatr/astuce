
import ast, sys, io
import logging
from typing import Any, List
from textwrap import dedent

import pytest, unittest

from astuce import inference, setup_logger, nodes, parser, _typing

require_version = lambda _v:pytest.mark.skipif(sys.version_info < _v, reason=f"requires python {'.'.join((str(v) for v in _v))}")

def extract_node(expr: str, modname: str = 'test', allow_stmt: bool = False) -> nodes.ASTNode:
    """
    Convert a python **expression** to ast. 
    Can raise `SyntaxError` if invalid python sytax or if got statements instead of expression.
    """
    _astuce = parser.Parser()

    try:
        statements = _astuce.parse(expr, modname=modname).body
    except SyntaxError as e:
        raise SyntaxError(str(e)) from e
    if len(statements) != 1:
        raise SyntaxError("Expected expression, got multiple statements")
    stmt, = statements
    if isinstance(stmt, ast.Expr):
        # Expression wrapped in an Expr statement.
        return stmt.value
    elif not allow_stmt:
        raise SyntaxError("Expected expression, got statement")
    else:
        return stmt


def fromtext(text:str, modname:str='test') -> ast.Module:
    # test fucntion
    return parser.Parser().parse(dedent(text), modname)

class AstuceTestCase(unittest.TestCase):

    def setUp(self):
        self.parser = parser.Parser()

    def parse(self, source:str, modname:str='test', **kw:Any) -> _typing.Module:
        return self.parser.parse(dedent(source), modname, **kw)

_logger = setup_logger(verbose=True)

class capture_output(list):        
    def __enter__(self):
        self._stream = io.StringIO()
        self.handler = logging.StreamHandler(self._stream)
        self.handler.setLevel(logging.DEBUG)
        self.handler.setFormatter(logging.Formatter("%(message)s"))
        _logger.addHandler(self.handler)

        return self

    def __exit__(self, *args):
        self._stream.flush()
        self.extend(self._stream.getvalue().splitlines())
        _logger.removeHandler(self.handler)

def get_load_names(node:_typing.ASTNode, name:str) -> List[ast.Name]:
    return [n for n in nodes.nodes_of_class(
        node, ast.Name, 
        predicate= lambda n: nodes.get_context(n) == nodes.Context.Load) 
        
        if n.id == name]

def get_exprs(nodes:List[_typing.ASTNode]) -> List[_typing.ASTexpr]:
    """
    Get all expressions wrapped inside ast.Expr in the list, 
    except the one added by astuce.
    """
    filtered_body = [o.value for o in filter(
            lambda o: not inference._is_end_of_frame_sentinel(o) 
                and isinstance(o, ast.Expr), nodes)]
    return filtered_body
