"""
`ast.AST` inference utilities.

What is this?
=============

This is a derived work from `astroid <https://github.com/PyCQA/astroid>`_.

The aim of this module is to provide an enhanced version of the AST nodes 
that keeps 100% compatibility with the standard AST nodes.

The node classes have additional methods and attributes for different usages. 
Methods and attributes are added by patching ast classes.

They include some support for some simple static inference and local name scopes.

It works well with literals.

Why?
====

I needed a inference library that supports the standard AST nodes such that,
it can be used in `pydoctor <https://github.com/twisted/pydoctor>`_. 

This library can help:
 - Infer what's the value of complex ``__all__`` 
   variables and other literal constants across different modules. 
 - Trace back where a name was assigned, filtering ignorable statements.
 - Navigating in the tree with handy functions.

Limitations
===========

Astuce is smart, but not very. 

- It is intra-procedural: Does not try to infer what **value** a `ast.Call` might return in a generic manner.
  Type hints will be considered as a source of information to get the return type of a call, this is not a type checker.
- It is not path sensitive: Does not support constraints from `ast.If` blocks or assertions.
- It can't create AST by inspecting living objects.

.. TODO list all key function/methods in a table here.

Example usage
=============

.. python::

    from astuce import parser, inference

    p = parser.Parser() 

    mod1 = p.parse('''
    from mod2 import __all__ as _l
    __all__ = ['f', 'k']
    __all__.extend(_l)
    ''', modname='mod1')

    mod2 = p.parse('''
    __all__ = ('i', 'j')
    ''', modname='mod2')

    inferred = list(inference.infer_attr(mod2, '__all__'))
    assert len(inferred) == 1
    assert ast.literal_eval(inferred[0]) == ['f', 'k', 'i', 'j']

"""

import ast
import logging
import sys
from typing import TextIO

from .nodes import ASTNode, Instance
from .monkey import MonkeyPatcher

##### Logger setup

def setup_logger(
    *,
    name: str = 'astuce',
    verbose: bool = False,
    quiet: bool = False,
    stream: TextIO = sys.stdout,
    format_string: str = "%(message)s",
    ) -> logging.Logger:
    """
    Utility to (re)setup astuce's stream logger.
    """
    
    if verbose: verb_level = logging.DEBUG
    elif quiet: verb_level = logging.ERROR
    else: verb_level = logging.INFO
    
    std = logging.StreamHandler(stream)
    std.setLevel(verb_level)
    std.setFormatter(logging.Formatter(format_string))
    
    log = logging.getLogger(name)
    log.handlers = [std]
    return log

setup_logger(quiet=True)

##### Dynamically patch the ast.AST classes.

_patcher = MonkeyPatcher()

_patcher.addMixinPatch(ast, "Constant", [ASTNode, Instance])
_patcher.addMixinPatch(ast, "List", [ASTNode, Instance])
_patcher.addMixinPatch(ast, "Tuple", [ASTNode, Instance])
_patcher.addMixinPatch(ast, "Set", [ASTNode, Instance])
_patcher.addMixinPatch(ast, "Dict", [ASTNode, Instance])

if sys.version_info <= (3,6):
    # No need to add Instance at this point since this nodes are going to be transformed
    # to Constant nodes
    _patcher.addMixinPatch(ast, 'Num', [ASTNode])
    _patcher.addMixinPatch(ast, 'Bytes', [ASTNode])
    _patcher.addMixinPatch(ast, 'Str', [ASTNode])

_patcher.addMixinPatch(ast, 'Add', [ASTNode])
_patcher.addMixinPatch(ast, 'And', [ASTNode])
_patcher.addMixinPatch(ast, 'AnnAssign', [ASTNode])
_patcher.addMixinPatch(ast, 'Assert', [ASTNode])
_patcher.addMixinPatch(ast, 'Assign', [ASTNode])
_patcher.addMixinPatch(ast, 'AsyncFor', [ASTNode])
_patcher.addMixinPatch(ast, 'AsyncFunctionDef', [ASTNode])
_patcher.addMixinPatch(ast, 'AsyncWith', [ASTNode])
_patcher.addMixinPatch(ast, 'Attribute', [ASTNode])
_patcher.addMixinPatch(ast, 'AugAssign', [ASTNode])
_patcher.addMixinPatch(ast, 'Await', [ASTNode])
_patcher.addMixinPatch(ast, 'BinOp', [ASTNode])
_patcher.addMixinPatch(ast, 'BitAnd', [ASTNode])
_patcher.addMixinPatch(ast, 'BitOr', [ASTNode])
_patcher.addMixinPatch(ast, 'BitXor', [ASTNode])
_patcher.addMixinPatch(ast, 'BoolOp', [ASTNode])
_patcher.addMixinPatch(ast, 'Break', [ASTNode])
_patcher.addMixinPatch(ast, 'Call', [ASTNode])
_patcher.addMixinPatch(ast, 'ClassDef', [ASTNode])
_patcher.addMixinPatch(ast, 'Compare', [ASTNode])
_patcher.addMixinPatch(ast, 'Continue', [ASTNode])
_patcher.addMixinPatch(ast, 'Del', [ASTNode])
_patcher.addMixinPatch(ast, 'Delete', [ASTNode])
_patcher.addMixinPatch(ast, 'DictComp', [ASTNode])
_patcher.addMixinPatch(ast, 'Div', [ASTNode])
_patcher.addMixinPatch(ast, 'Ellipsis', [ASTNode])
_patcher.addMixinPatch(ast, 'Eq', [ASTNode])
_patcher.addMixinPatch(ast, 'ExceptHandler', [ASTNode])
_patcher.addMixinPatch(ast, 'Expr', [ASTNode])
_patcher.addMixinPatch(ast, 'Expression', [ASTNode])
_patcher.addMixinPatch(ast, 'ExtSlice', [ASTNode])
_patcher.addMixinPatch(ast, 'FloorDiv', [ASTNode])
_patcher.addMixinPatch(ast, 'For', [ASTNode])
_patcher.addMixinPatch(ast, 'FormattedValue', [ASTNode])
_patcher.addMixinPatch(ast, 'FunctionDef', [ASTNode])
_patcher.addMixinPatch(ast, 'FunctionType', [ASTNode])
_patcher.addMixinPatch(ast, 'GeneratorExp', [ASTNode])
_patcher.addMixinPatch(ast, 'Global', [ASTNode])
_patcher.addMixinPatch(ast, 'Gt', [ASTNode])
_patcher.addMixinPatch(ast, 'GtE', [ASTNode])
_patcher.addMixinPatch(ast, 'If', [ASTNode])
_patcher.addMixinPatch(ast, 'IfExp', [ASTNode])
_patcher.addMixinPatch(ast, 'Import', [ASTNode])
_patcher.addMixinPatch(ast, 'ImportFrom', [ASTNode])
_patcher.addMixinPatch(ast, 'In', [ASTNode])
_patcher.addMixinPatch(ast, 'Index', [ASTNode])
_patcher.addMixinPatch(ast, 'Interactive', [ASTNode])
_patcher.addMixinPatch(ast, 'Invert', [ASTNode])
_patcher.addMixinPatch(ast, 'Is', [ASTNode])
_patcher.addMixinPatch(ast, 'IsNot', [ASTNode])
_patcher.addMixinPatch(ast, 'JoinedStr', [ASTNode])
_patcher.addMixinPatch(ast, 'LShift', [ASTNode])
_patcher.addMixinPatch(ast, 'Lambda', [ASTNode])
_patcher.addMixinPatch(ast, 'ListComp', [ASTNode])
_patcher.addMixinPatch(ast, 'Load', [ASTNode])
_patcher.addMixinPatch(ast, 'Lt', [ASTNode])
_patcher.addMixinPatch(ast, 'LtE', [ASTNode])
_patcher.addMixinPatch(ast, 'MatMult', [ASTNode])
_patcher.addMixinPatch(ast, 'Mod', [ASTNode])
_patcher.addMixinPatch(ast, 'Module', [ASTNode])
_patcher.addMixinPatch(ast, 'Mult', [ASTNode])
_patcher.addMixinPatch(ast, 'Name', [ASTNode])
_patcher.addMixinPatch(ast, 'Nonlocal', [ASTNode])
_patcher.addMixinPatch(ast, 'Not', [ASTNode])
_patcher.addMixinPatch(ast, 'NotEq', [ASTNode])
_patcher.addMixinPatch(ast, 'NotIn', [ASTNode])
_patcher.addMixinPatch(ast, 'Or', [ASTNode])
_patcher.addMixinPatch(ast, 'Pass', [ASTNode])
_patcher.addMixinPatch(ast, 'Pow', [ASTNode])
_patcher.addMixinPatch(ast, 'RShift', [ASTNode])
_patcher.addMixinPatch(ast, 'Raise', [ASTNode])
_patcher.addMixinPatch(ast, 'Return', [ASTNode])
_patcher.addMixinPatch(ast, 'SetComp', [ASTNode])
_patcher.addMixinPatch(ast, 'Slice', [ASTNode])
_patcher.addMixinPatch(ast, 'Starred', [ASTNode])
_patcher.addMixinPatch(ast, 'Store', [ASTNode])
_patcher.addMixinPatch(ast, 'Sub', [ASTNode])
_patcher.addMixinPatch(ast, 'Subscript', [ASTNode])
_patcher.addMixinPatch(ast, 'Suite', [ASTNode])
_patcher.addMixinPatch(ast, 'Try', [ASTNode])
_patcher.addMixinPatch(ast, 'TypeIgnore', [ASTNode])
_patcher.addMixinPatch(ast, 'UAdd', [ASTNode])
_patcher.addMixinPatch(ast, 'USub', [ASTNode])
_patcher.addMixinPatch(ast, 'UnaryOp', [ASTNode])
_patcher.addMixinPatch(ast, 'While', [ASTNode])
_patcher.addMixinPatch(ast, 'With', [ASTNode])
_patcher.addMixinPatch(ast, 'Yield', [ASTNode])
_patcher.addMixinPatch(ast, 'YieldFrom', [ASTNode])
_patcher.addMixinPatch(ast, 'alias', [ASTNode])
_patcher.addMixinPatch(ast, 'arg', [ASTNode])
_patcher.addMixinPatch(ast, 'arguments', [ASTNode])
_patcher.addMixinPatch(ast, 'comprehension', [ASTNode])
_patcher.addMixinPatch(ast, 'keyword', [ASTNode])
_patcher.addMixinPatch(ast, 'slice', [ASTNode])
_patcher.addMixinPatch(ast, 'withitem', [ASTNode])

# Deprecated in 3.8; use Constant
_patcher.addMixinPatch(ast, 'NameConstant', [ASTNode])

if sys.version_info >= (3,8):
    _patcher.addMixinPatch(ast, 'NamedExpr', [ASTNode])

if sys.version_info >= (3,11):
    _patcher.addMixinPatch(ast, 'TryStar', [ASTNode])

if sys.version_info >= (3,10):
    _patcher.addMixinPatch(ast, 'match_case', [ASTNode])
    _patcher.addMixinPatch(ast, 'Match', [ASTNode])
    _patcher.addMixinPatch(ast, 'MatchAs', [ASTNode])
    _patcher.addMixinPatch(ast, 'MatchClass', [ASTNode])
    _patcher.addMixinPatch(ast, 'MatchMapping', [ASTNode])
    _patcher.addMixinPatch(ast, 'MatchOr', [ASTNode])
    _patcher.addMixinPatch(ast, 'MatchSequence', [ASTNode])
    _patcher.addMixinPatch(ast, 'MatchSingleton', [ASTNode])
    _patcher.addMixinPatch(ast, 'MatchStar', [ASTNode])
    _patcher.addMixinPatch(ast, 'MatchValue', [ASTNode])

_patcher.patch()
