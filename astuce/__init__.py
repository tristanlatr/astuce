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
    assert inferred[0].literal_eval() == ['f', 'k', 'i', 'j']

"""

import ast
import inspect
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

_patched = False

def _patch_ast() -> None:
    """Extend the base `ast.AST` class to provide more functionality."""
    patcher = MonkeyPatcher()
    global _patched  # noqa: WPS420
    if _patched:
        return
    
    # Patch
    for name, member in inspect.getmembers(ast):
        # TODO: List all classes
        if name not in ["AST",
             "stmt", 
             "expr", 
             "operator", 
             "mod", 
             "expr_context",
             "boolop",
             "unaryop",
             "cmpop",
             "excepthandler",
             "type_ignore", # Ignore classes that are not concrete
             ] and inspect.isclass(member):
            
            if name in ["Constant", "List", "Tuple", "Set", "Dict"]:
                patcher.addMixinPatch(ast, name, [ASTNode, Instance])
            elif issubclass(member, ast.AST) and ASTNode not in member.mro():
                patcher.addMixinPatch(ast, name, [ASTNode])
    patcher.patch()
    _patched = True  # noqa: WPS122,WPS442

_patch_ast()
