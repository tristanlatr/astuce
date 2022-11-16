"""
This module provides a replacement for `ast.parse` function. 

The only breaking change compared to the standard library `ast` module 
is the signature of the `parse` function. 
"""

__docformat__ = 'restructuredtext'

from functools import lru_cache, partial
import warnings
import sys
import ast
from typing import Any, Callable, Dict, Iterator, List, Optional, Union, cast

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


from .nodes import _END_OF_FRAME_SENTINEL_CONSTANT, ASTNode, Instance, is_assign_name, is_del_name, is_scoped_node, fix_ast
from . import _typing, _context, cfg


def _set_local(self:'_typing.ASTNode', name:str, node:'ast.AST') -> None:
    """Define that the given name is declared in the given statement node.

    .. seealso:: `ASTNode.scope`

    :param name: The name that is being defined.
    :type name: str

    :param node: The node that defines the given name (i.e ast.Name objects).
    :type node: ASTNode
    """
    if isinstance(self, ast.NamedExpr):
        return _set_local(self.frame, name, node)
    if not is_scoped_node(self):
        return _set_local(self.parent, name, node)

    # nodes that can be stored in the locals dict
    LOCALS_ASSIGN_NAME_NODES = (ast.ClassDef, 
                                ast.FunctionDef, 
                                ast.AsyncFunctionDef, 
                                ast.Name, 
                                ast.arg, 
                                ast.alias) 

        # ast.Attribute not supported at the moment, 
        # analysing assigments outside out the scope needs more work.
    
    assert isinstance(node, LOCALS_ASSIGN_NAME_NODES), f"cannot set {node} as local"
    assert not node in self.locals.get(name, ()), (self, node)
    self.locals.setdefault(name, []).append(node) # type:ignore[arg-type]

class _AstuceModuleVisitor(ast.NodeTransformer):
    """
    Obviously inspired by astroid rebuilder
    """
    # custom ast.AT attributes are: 
    # '_parser' and 'parent' on all nodes
    # '_modname', '_is_package' and '_filename' on module nodes
    # '_locals' on scoped nodes
    # 'type_info' on instance nodes

    parent: ASTNode = cast('ASTNode', None)

    def __init__(self, parser:'Parser') -> None:
        super().__init__()
        self.parser = parser
    
    def visit(self, node: ASTNode) -> Optional[_typing.ASTNode]:

        # Set the 'parent' and '_parser' attributes on all nodes.
        self.parser._init_new_node(node, self.parent)

        self.parent = node # push new parent

        r = super().visit(cast(ast.AST, node))

        self.parent = node.parent # pop new parent
        
        if self.parent is None:
            assert isinstance(node, ast.Module)
        
        return r

    def _get_end_of_frame_sentinel(self) -> ast.stmt:
        return ast.Expr(ast.Constant(_END_OF_FRAME_SENTINEL_CONSTANT))
    
    def visit_Module(self, node:_typing.Module) -> _typing.Module:
        # append "end of" statement
        node.body += (self._get_end_of_frame_sentinel(),)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: _typing.FunctionDef) -> _typing.FunctionDef:
        _set_local(node.parent, node.name, node)
        # append "end of" statement
        node.body += (self._get_end_of_frame_sentinel(),)
        return self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: _typing.AsyncFunctionDef) -> _typing.AsyncFunctionDef:
        _set_local(node.parent, node.name, node)
        # append "end of" statement
        node.body += (self._get_end_of_frame_sentinel(),)
        return self.generic_visit(node)
    
    def visit_ClassDef(self, node: _typing.ClassDef) -> _typing.ClassDef:
        _set_local(node.parent, node.name, node)
        # append "end of" statement
        node.body += (self._get_end_of_frame_sentinel(),)
        return self.generic_visit(node)
    
    def visit_Import(self, node: _typing.Import) -> _typing.Import:
        # save import names in parent's locals:
        for a in node.names:
            
            # When ``import x.y``, we don't need the `.y` part
            # It's currently sufficient to track the information
            # TODO: 
            # by confusing ``x.y`` with ``x``,
            # we might not be able to detect some AttributeError:
            
            # >>> import collections
            # >>> collections.abc.Sized
            # Traceback (most recent call last):
            # File "<stdin>", line 1, in <module>
            # File "/collections/__init__.py", line 55, in __getattr__
            #     raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
            # AttributeError: module 'collections' has no attribute 'abc'
            
            # With the current design we 
            # cannot track whether the abc module has been imported
            # explicitely or only accessed like an attribute.

            name = a.asname or a.name 
            _set_local(node.parent, name.split(".")[0], a)
        return self.generic_visit(node)

    def visit_ImportFrom(self, node: _typing.ImportFrom) -> _typing.ImportFrom:
        if any(a.name=='*' for a in node.names):
            # store wildcard imports to be resolved after
            self.parser._wildcard_import.append(node)
        else:
            for a in node.names:
                name = a.asname or a.name
                _set_local(node.parent, name, a)
        return self.generic_visit(node)
    
    def visit_arg(self, node: _typing.arg) -> _typing.arg:
        _set_local(node.parent, node.arg, node)
        return self.generic_visit(node)
    
    def visit_Name(self, node: _typing.Name) -> _typing.Name:
        if is_assign_name(node) or is_del_name(node):
            _set_local(node.parent, node.id, node)
        return self.generic_visit(node)
    
    def visit_Attribute(self, node: _typing.Attribute) -> _typing.Attribute:
        if is_assign_name(node) and (not 
          # Prohibit a local save if we are in an ExceptHandler.
          any(isinstance(o, ast.ExceptHandler) for o in node.node_ancestors())):
            self.parser._assignattr.append(node)
        return self.generic_visit(node)
    
    # Transform statement level __all__.extend() and __all__.append() into augmented assignments
    # TODO: think of a more extensible way to transform the tree, it should not be necessary to traverse it twise, though.
    def visit_Expr(self, node:_typing.Expr) -> Union[_typing.Expr, _typing.AugAssign]:
        v = node.value
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute):
            o = v.func.value
            a = v.func.attr

            if len(v.args)==1 and len(v.keywords)==0:
                # We can safely apply this transformation because we know __all__ should be a list or tuple.
                if isinstance(o, ast.Name) and o.id == '__all__':
                    aug = None
                    if a == 'extend':
                        node._report("Transforming __all__.extend() into an augmented assigment")
                        aug = ast.AugAssign(ast.Name(o.id, ast.Store()), ast.Add(), v.args[0])
                    elif a == 'append':
                        node._report("Transforming __all__.append() into an augmented assigment")
                        aug = ast.AugAssign(ast.Name(o.id, ast.Store()), ast.Add(), ast.List(elts=[v.args[0]]))
                    if aug:
                        return fix_ast(self.visit(aug), parent=node.parent)

        return self.generic_visit(node)

class Parser:
    """
    Object to keep track of parsed modules and inferred nodes.
    """
    max_inferable_values = 42

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

        self._inference_cache: _context._InferenceCache = {}
        """
        Inferred node contexts to their mapped results.

        The keys are nodes and the value is tuple of the inferred results.

        :see: `InferenceContext._cache`
        """
        # Since astuce in not inter-procedural, like astroid, we don't have 
        # to use the boundnode, callcontext, ect 
    
    def invalidate_inference_cache(self) -> None:
        """
        Clears the inference cache.
        """
        self._inference_cache.clear()

    # @lru_cache
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

    def parse(self, source:str, modname:str, *, is_package:bool=False, **kw:Any) -> _typing.Module:
        """
        Parse the python source string into a `ast.Module` instance, and make compatible with astuce inference system.

        :Parameters:
        source
            The python code string.
        modname
            The full name of the module, required. 
            This additional argument is the only breaking changed compared to `ast.parse`.
        is_package
            Whether this module is package.
        kw
            Other arguments are passed to the `ast.parse` function directly.
            Including:

            - ``filename``: The filename where we can find the module source
                (only used for error messages)
        """
        mod = cast(_typing.Module, _parse(source, **kw))
        return self.add(mod, modname, is_package=is_package, **kw)
    
    def add(self, mod:ast.Module, modname:str, *, is_package:bool=False, **kw:Any) -> _typing.Module:
        """
        Add a module to the parser and make compatible with astuce inference system.

        This method will apply a set of harmless transformations::
            
            __all__.extend(a) -> __all__ += a
            __all__.append(a) -> __all__ += [a]
        """
        
        # Store whether this module is a package
        if is_package:
            mod._is_package = True
        
        # Store module file name
        filename = kw.get('filename')
        if filename:
            mod._filename = filename
        
        # Store module name
        mod._modname = modname
        self.modules[modname] = mod

        # Invalidate inference cache
        self.invalidate_inference_cache()

        # Add attributes to AST nodes, build locals, apply transformations.
        return _AstuceModuleVisitor(self).visit(mod)

    def _new_context(self) -> _context.InferenceContext:
        """
        Create a fresh inference context.
        """
        return _context.copy_context(None, cache=self._inference_cache)

    def _init_new_node(self, node:'ASTNode', parent: 'ASTNode') -> None:
        """
        A method that must be called for all nodes in the tree as well as inferred (created) nodes.
        """
        node.parent = parent
        node._parser = self

        # Set '_locals' attribute on scoped nodes only
        if is_scoped_node(node):
            if getattr(node, '_locals', None) is None:
                node._locals = {}
        
        # Init instance 'type_info' attribute
        if isinstance(node, Instance):
            if getattr(node, 'type_info', None) is None:
                node._init_type_info()
        

_default_parser = Parser()
def parse(source:str, modname:str, is_package:bool=False, **kw:Any) -> _typing.Module:
    """
    Parse the python source string into a `ast.Module` instance.
    
    :see: `Parser.parse`
    
    Attention, using this function alters a global parser state, use a `Parser` instance
    to parse a set of modules in isolated environments.
    """
    return _default_parser.parse(source, modname, is_package=is_package, **kw)
