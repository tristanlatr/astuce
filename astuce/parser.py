"""
This module provides a replacement for `ast.parse` function. 

The only breaking change compared to the standard library `ast` module 
is the signature of the `parse` function. 
"""

__docformat__ = 'restructuredtext'

from functools import partial
import sys
import ast
from typing import Any, Dict, List, Optional, cast

if sys.version_info >= (3,8):
    _parse = partial(ast.parse, type_comments=True)
else:
    _parse = ast.parse

from .nodes import ASTNode, get_context, Context, is_assign_name, is_del_name, is_scoped_node
from . import _typing

class _AstuceModuleVisitor(ast.NodeVisitor):
    """
    Obviously inspired by astroid rebuilder
    """

    parent: ASTNode = cast('ASTNode', None)

    def __init__(self, parser:'Parser') -> None:
        super().__init__()
        self.parser = parser
    
    def visit(self, node: ASTNode) -> None: # type:ignore[override]

        # Set the 'parent' attribute
        node.parent = self.parent
        self.parent = node

        # Set '_astuce' attribute on all nodes.
        node._parser = self.parser

        # Set '_locals' attribute on scoped nodes only
        if is_scoped_node(node):
            node._locals = {}
        
        super().visit(node)

        self.parent = node.parent
        if self.parent == None:
            assert isinstance(node, ast.Module)
    

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.parent._set_local(node.name, node)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.parent._set_local(node.name, node)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.parent._set_local(node.name, node)
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import) -> None:
        # save import names in parent's locals:
        for a in node.names:
            name = a.asname or a.name
            self.parent._set_local(name.split(".")[0], node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if any(a.name=='*' for a in node.names):
            # store wildcard imports to be resolved after
            self.parser._wildcard_import.append(node)
        else:
            for a in node.names:
                name = a.asname or a.name
                self.parent._set_local(name, node)
        self.generic_visit(node)
    
    def visit_arg(self, node: ast.arg) -> None:
        self.parent._set_local(node.arg, node)
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name) -> None:

        if is_assign_name(node) or is_del_name(node):
            self.parent._set_local(node.id, node)

        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute) -> None:

        if is_assign_name(node) and (not 
          # Prohibit a local save if we are in an ExceptHandler.
          any(isinstance(o, ast.ExceptHandler) for o in node.node_ancestors())): # type:ignore[attr-defined]
            self.parser._assignattr.append(node)

        self.generic_visit(node)

class Parser:
    """
    Object to keep track of parsed modules.
    """

    def __init__(self) -> None:
        self.modules:Dict[str, ast.Module] = {}
        """
        The parsed modules.
        """

        self._assignattr:List[ast.Attribute] = []
        """
        A list to store assignments to attributes. 

        We might want to resolve them after building.
        """

        self._wildcard_import:List[ast.ImportFrom] = []
        """
        Store wildcard ImportFrom to resolve them after building.
        """

    def parse(self, source:str, modname:str, is_package:bool=False, **kw:Any) -> ast.Module:
        """
        Parse the python source string into a `ast.Module` instance.
        """
        mod = _parse(source, **kw)
        
        if is_package:
            mod._is_package = True
        
        mod._modname = modname
        self.modules[modname] = mod

        _AstuceModuleVisitor(self).visit(cast(ASTNode, mod))
        return mod

_default_parser = Parser()
def parse(source:str, modname:str, is_package:bool=False, **kw:Any) -> ast.Module:
    """
    Parse the python source string into a `ast.Module` instance.

    :Parameters:
        source
            The python code string.
        modname
            The full name of the module, required. 
            This additional argument is the only breaking changed compared to `ast.parse`.
        kw
            Other arguments are passed to the `ast.parse` function directly.
            Including:

            - ``filename``: The filename where we can find the module source
                (only used for ast error messages)
    """
    return _default_parser.parse(source, modname, is_package=is_package, **kw)
