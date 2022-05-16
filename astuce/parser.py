"""
This module provides a replacement for `ast.parse` function. 

The only breaking change compared to the standard library `ast` module 
is the signature of the `parse` function. 
"""

__docformat__ = 'restructuredtext'

from functools import partial
import warnings
import sys
import ast
from typing import Any, Callable, Dict, List, Optional, cast

if sys.version_info >= (3,8):
    _parse = partial(ast.parse, type_comments=True)
else:
    _parse = ast.parse

# Try very hard to import a full-complete unparse() function.
# Fallback to code in _astunparse.py if function could be imported 
# either from the standard library from python 3.9 or from 'astunparse' or 'astor' library.
_unparse: Callable[[ast.AST], str]
if sys.version_info >= (3,9):
    _unparse = ast.unparse
else:
    try:
        import astunparse
        _unparse = astunparse.unparse
    except ImportError:
        try:
            import astor
            _unparse = astor.to_source
        except ImportError:
            from . import _astunparse 
            _unparse = _astunparse.unparse

from .nodes import ASTNode, get_context, Context, is_assign_name, is_del_name, is_scoped_node
from . import _typing, exceptions

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
        node.parent._set_local(node.name, node)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        node.parent._set_local(node.name, node)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        node.parent._set_local(node.name, node)
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import) -> None:
        # save import names in parent's locals:
        for a in node.names:
            name = a.asname or a.name
            node.parent._set_local(name.split(".")[0], node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if any(a.name=='*' for a in node.names):
            # store wildcard imports to be resolved after
            self.parser._wildcard_import.append(node)
        else:
            for a in node.names:
                name = a.asname or a.name
                node.parent._set_local(name, node)
        self.generic_visit(node)
    
    def visit_arg(self, node: ast.arg) -> None:
        node.parent._set_local(node.arg, node)
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name) -> None:

        if is_assign_name(node) or is_del_name(node):
            node.parent._set_local(node.id, node)

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
        self.modules:Dict[str, _typing.Module] = {}
        """
        The parsed modules.
        """

        self._assignattr:List[_typing.Attribute] = []
        """
        A list to store assignments to attributes. 

        We might want to resolve them after building.
        """

        self._wildcard_import:List[_typing.ImportFrom] = []
        """
        Store wildcard ImportFrom to resolve them after building.
        """
    
    def unparse(self, node: ast.AST) -> str:
        """
        Unparse an ast.AST object and generate a code string.
        """
        strip_extra_parenthesis = True # could be made an argument?
        try:
            unparsed = _unparse(node).strip()
            # Workaround the extra parenthesis added by the unparse() function.
            if strip_extra_parenthesis and unparsed.startswith('(') and unparsed.endswith(')'):
                unparsed = unparsed[1:-1]
            return unparsed
        except Exception as e:
            raise ValueError(f"can't unparse {node}") from e

    def parse(self, source:str, modname:str, is_package:bool=False, **kw:Any) -> _typing.Module:
        """
        Parse the python source string into a `ast.Module` instance.
        """
        mod = _parse(source, **kw)
        
        # Store whether this module is package
        if is_package:
            mod._is_package = True
        
        # Store module file name
        filename = kw.get('filename')
        if filename:
            mod._filename = filename
        
        # Store module name
        mod._modname = modname
        self.modules[modname] = mod

        # Build locals 
        _AstuceModuleVisitor(self).visit(cast(ASTNode, mod))
        return cast(_typing.Module, mod)
    
    def _report(self, descr: str, lineno_offset: int = 0) -> None:
        """Log an error or warning about this node object."""

        def description(node: ASTNode) -> str:
            """A string describing our source location to the user.

            If this module's code was read from a file, this returns
            its file path. In other cases, such as during unit testing,
            the full module name is returned.
            """
            source_path = node.root._filename
            return node.root.qname if source_path is None else str(source_path)

        linenumber: object
        linenumber = self.line
        if linenumber:
            linenumber += lineno_offset
        elif lineno_offset and self.root is self:
            linenumber = lineno_offset
        else:
            linenumber = '???'

        warnings.warn(f'{description(self)}:{linenumber}: {descr}', category=exceptions.StaticAnalysisWarning)

_default_parser = Parser()
def parse(source:str, modname:str, is_package:bool=False, **kw:Any) -> _typing.Module:
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
    
    Attention, using this function alters some global state, use a `Parser` instance
    to parse modules in isolated environments.
    
    """
    return _default_parser.parse(source, modname, is_package=is_package, **kw)
