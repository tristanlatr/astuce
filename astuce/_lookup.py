"""
Code driving the ASTNode.lookup() method.

See also ``filter_statements.py``.
"""
import builtins
from typing import List, Tuple, cast
import ast

from . import _typing

_builtins_names = dir(builtins)

def lookup(self:'_typing.ASTNode', name:str, offset:int) -> None:
    from astuce import nodes
    if nodes.is_scoped_node(self):
        return _scope_lookup(self, self, name, offset=offset)
    return _scope_lookup(self.scope, self, name, offset=offset)

def _scope_lookup(self:'_typing.ASTNode', node: '_typing.ASTNode', name:str, offset:int=0) -> Tuple['_typing.ASTNode', List['_typing.ASTNode']]:
    if isinstance(self, ast.Module):
        return _module_lookup(self, node, name, offset)
    elif isinstance(self, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _function_lookup(self, node, name, offset)
    elif isinstance(self, ast.ClassDef):
        return _class_lookup(self, node, name, offset)
    else:
        return _base_scope_lookup(self, node, name, offset)

def _module_lookup(self:'_typing.ASTNode', node: '_typing.ASTNode', name:str, offset:int=0) -> Tuple['_typing.ASTNode', List['_typing.ASTNode']]:
    # TODO: Handle {"__name__", "__doc__", "__file__", "__path__", "__package__"}
    """The names of module attributes available through the global scope."""

    return _base_scope_lookup(self, node, name, offset)

def _class_lookup(self:'_typing.ASTNode', node: '_typing.ASTNode', name:str, offset:int=0) -> Tuple['_typing.ASTNode', List['_typing.ASTNode']]:
    # TODO: Handle __module__, __qualname__,
    assert isinstance(self, ast.ClassDef)

    # If the name looks like a builtin name, just try to look
    # into the upper scope of this class. We might have a
    # decorator that it's poorly named after a builtin object
    # inside this class.
    lookup_upper_frame = (
        node.parent.locate_child(node)[0] == 'decorator_list'
        and name in _builtins_names
    )
    if (
        any(node == base or base.parent_of(node) for base in self.bases)
        or lookup_upper_frame
    ):
        # Handle the case where we have either a name
        # in the bases of a class, which exists before
        # the actual definition or the case where we have
        # a Getattr node, with that name.
        #
        # name = ...
        # class A(name):
        #     def name(self): ...
        #
        # import name
        # class A(name.Name):
        #     def name(self): ...

        frame:_typing.FrameNodeT = self.parent.frame
        # line offset to avoid that class A(A) resolve the ancestor to
        # the defined class
        offset = -1
    else:
        frame = cast(_typing.ClassDef, self)
    return _base_scope_lookup(frame, node, name, offset)

def _function_lookup(self:'_typing.ASTNode', node: '_typing.ASTNode', name:str, offset:int=0) -> Tuple['_typing.ASTNode', List['_typing.ASTNode']]:
    assert isinstance(self, (ast.FunctionDef, ast.AsyncFunctionDef))
    
    if name == "__class__":
        # __class__ is an implicit closure reference created by the compiler
        # if any methods in a class body refer to either __class__ or super.
        # In our case, we want to be able to look it up in the current scope
        # when `__class__` is being used.
        frame = self.parent.frame
        if isinstance(frame, ast.ClassDef):
            return self, [frame] # type:ignore[return-value, list-item]

    if node in self.args.defaults or node in self.args.kw_defaults:
        frame = self.parent.frame
        # line offset to avoid that def func(f=func) resolve the default
        # value to the defined function
        offset = -1
    else:
        # check this is not used in function decorators
        frame = self # type:ignore
    return _base_scope_lookup(frame, node, name, offset)

def _base_scope_lookup(self:'_typing.ASTNode', node: '_typing.ASTNode', name:str, offset:int=0) -> Tuple['_typing.ASTNode', List['_typing.ASTNode']]:
    """XXX method for interfacing the scope lookup"""

    from .filter_statements import filter_stmts # workaround cyclic imports.

    try:
        stmts = filter_stmts(node, self.locals[name], self, offset)
    except KeyError:
        stmts = []
    if stmts:
        return self, stmts

    # Handle nested scopes: since class names do not extend to nested
    # scopes (e.g., methods), we find the next enclosing non-class scope
    pscope = self.parent and self.parent.scope
    while pscope is not None:
        if not isinstance(pscope, ast.ClassDef):
            return _scope_lookup(pscope, node, name)
        pscope = pscope.parent and pscope.parent.scope
    
    # self is at the top level of a module, and we couldn't find references to this name
    return (node, []) #type:ignore[unreachable]
    # NameInferenceError is raised by callers.
    # raise LookupError(f"couldn't find references to {name!r}")
