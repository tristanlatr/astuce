
import enum
from functools import lru_cache
import functools
import re
from typing import Any, Callable, Dict, Iterable, Iterator, Optional, Sequence, List, Tuple, Type, Union, cast, TYPE_CHECKING, overload
import sys
import ast
from ast import AST
import warnings

import attr

from astuce import exceptions, _lookup

# TODO: remove once Python 3.7 support is dropped
if sys.version_info < (3, 8):
    from cached_property import cached_property
else:
    from functools import cached_property  # noqa: WPS440

from .exceptions import LastNodeError, RootNodeError
from . import _typing, _astutils

if TYPE_CHECKING:
    from .parser import Parser
    from ._context import OptionalInferenceContext

@object.__new__
class Uninferable:
    """Special object which is returned when inference fails."""

    def __repr__(self) -> str:
        return "<Uninferable>"

    __str__ = __repr__

    # TODO: Is this code required?
    # def __getattribute__(self, name):
    #     if name.startswith("__") and name.endswith("__"):
    #         return object.__getattribute__(self, name)
    #     return self

    # def __call__(self, *args, **kwargs):
    #     return self

    def __bool__(self) -> bool:
        return False


class ASTNode:
    """
    This class is dynamically added to the bases of each AST node class.
    
    :var lineno: 
        - Modules lineno -> 0
        - Missing lineno information -> -1 (should not happend)

    """

    parent: '_typing.ASTNode' = None # type:ignore
    """
    `None` for Modules.
    """
    
    _locals: Dict[str, List[_typing.LocalsAssignT]] = None # type:ignore
    _parser: 'Parser' = None # type:ignore
    _modname: Optional[str] = None
    _is_package: bool = False
    _filename: Optional[str] = None

    @cached_property
    def root(self) -> _typing.Module:
        """Return the root node of the syntax tree.

        :returns: The root node.
        :rtype: Module
        """
        if self.parent:
            return self.parent.root
        assert isinstance(self, ast.Module)
        return self # type:ignore[return-value]
    
    @cached_property
    def lineno(self) -> int:
        if isinstance(self, ast.Module):
            return 0
        return getattr(super(), 'lineno', -1)

    @property
    def qname(self) -> str:
        """Get the 'qualified' name of the node.

        For example: module.name, module.class.name ...

        :returns: The qualified name.
        :rtype: str
        """
        if isinstance(self, ast.Module):
            assert self._modname is not None
            return self._modname
        assert isinstance(self, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)), "use 'qname' only on frame nodes"
        return f"{self.parent.frame.qname}.{self.name}"

    @cached_property
    def locals(self) -> Dict[str, List[_typing.LocalsAssignT]]:
        assert is_scoped_node(self), "use 'locals' only on scoped nodes"
        return self._locals
    
    # TODO: remove once Python 3.7 support is dropped
    if sys.version_info < (3, 8):  # noqa: WPS604
        end_lineno = property(lambda node: None)

    @cached_property
    def kind(self) -> str:
        """Return the kind of this node.

        Returns:
            The node kind.
        """
        return self.__class__.__name__.lower()

    @cached_property
    def children(self) -> Sequence['_typing.ASTNode']:
        """Build and return the children of this node.

        Returns:
            A list of children.
        """
        return list(ast.iter_child_nodes(self)) # type:ignore

    @cached_property
    def position(self) -> int:
        """Tell the position of this node amongst its siblings.

        Raises:
            RootNodeError: When the node doesn't have a parent.

        Returns:
            The node position amongst its siblings.
        """
        if not isinstance(self, ast.Module):
            return self.parent.children.index(self)
        else:
            raise RootNodeError("the root node does not have a parent, nor siblings, nor a position")

    @cached_property
    def previous_siblings(self) -> Sequence['_typing.ASTNode']:
        """Return the previous siblings of this node, starting from the closest.

        Returns:
            The previous siblings.
        """
        if self.position == 0:
            return []
        return self.parent.children[self.position - 1 :: -1]

    @cached_property
    def next_siblings(self) -> Sequence['_typing.ASTNode']:
        """Return the next siblings of this node, starting from the closest.

        Returns:
            The next siblings.
        """
        if self.position == len(self.parent.children) - 1:
            return []
        return self.parent.children[self.position + 1 :]

    @cached_property
    def siblings(self) -> Sequence['_typing.ASTNode']:
        """Return the siblings of this node.

        Returns:
            The siblings.
        """
        return [*reversed(self.previous_siblings), *self.next_siblings]

    @cached_property
    def previous(self) -> '_typing.ASTNode':
        """Return the previous sibling of this node.

        Raises:
            LastNodeError: When the node does not have previous siblings.

        Returns:
            The sibling.
        """
        try:
            return self.previous_siblings[0]
        except IndexError as error:
            raise LastNodeError("there is no previous node") from error

    @cached_property  # noqa: A003
    def next(self) -> '_typing.ASTNode':  # noqa: A003
        """Return the next sibling of this node.

        Raises:
            LastNodeError: When the node does not have next siblings.

        Returns:
            The sibling.
        """
        try:
            return self.next_siblings[0]
        except IndexError as error:
            raise LastNodeError("there is no next node") from error

    @cached_property
    def first_child(self) -> '_typing.ASTNode':
        """Return the first child of this node.

        Raises:
            LastNodeError: When the node does not have children.

        Returns:
            The child.
        """
        try:
            return self.children[0]
        except IndexError as error:
            raise LastNodeError("there are no children node") from error

    @cached_property
    def last_child(self) -> '_typing.ASTNode':  # noqa: A003
        """Return the lasts child of this node.

        Raises:
            LastNodeError: When the node does not have children.

        Returns:
            The child.
        """
        try:
            return self.children[-1]
        except IndexError as error:
            raise LastNodeError("there are no children node") from error

    @cached_property
    def scope(self) -> _typing.ScopedNodeT:
        """
        The scope is which this expression can be resolved. This is generally equal to the frame, 
        expect for nodes defined in decorators, in this case the scope is the upper scope.

        Returns the first parent frame or generator/comprehension.

        When called on a :class:`Module` this returns self.
        """
        if isinstance(self, ast.Module):
            return cast(_typing.ScopedNodeT, self)

        if not self.parent:
            raise RootNodeError("parent missing")

        # special code for node inside function/class decorators, they should use the upper scope.
        if self._is_from_decorator:
            # the parent of a frame is always another frame, and a frame is always a scope ;-)
            return cast(_typing.FrameNodeT, self.frame.parent)

        # special code for NamedExpr
        if isinstance(self, ast.NamedExpr):
            # For certain parents NamedExpr evaluate to the scope of the parent
            if isinstance(self.parent, (ast.arguments, ast.keyword, ast.comprehension)):
                return self.parent.parent.parent.scope

        if isinstance(self, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef, ast.Module, 
                             ast.GeneratorExp, ast.DictComp, ast.SetComp, ast.ListComp, ast.Lambda)):
            return cast('_typing.ScopedNodeT', self)
        
        return self.parent.scope
    
    @cached_property
    def frame(self) -> _typing.FrameNodeT:
        """
        Returns the first parent `ast.Lambda`, `ast.FunctionDef`, `ast.AsyncFunctionDef`,`ast.ClassDef` or `ast.Module`.

        The parent of a frame is always another frame.
        
        Lambda frame is special because we can't define further locals except the one defined in the arguments.

        When called on a :class:`Module` this returns self.
        """
        if isinstance(self, ast.Module):
            return self # type:ignore[return-value]
        
        if not self.parent:
            raise RootNodeError("parent missing")

        # special code for NamedExpr
        if isinstance(self, ast.NamedExpr):
            # For certain parents NamedExpr evaluate to the scope of the parent
            if isinstance(self.parent, (ast.arguments, ast.keyword, ast.comprehension)):
                return self.parent.parent.parent.frame

        if isinstance(self, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef, ast.Lambda)):
            return cast('_typing.FrameNodeT', self)
        
        return self.parent.frame
    
    @cached_property
    def statement(self) -> Union[_typing.ASTstmt, _typing.Module]:
        """
        The first parent node, including self, marked as statement node.
        When called on a :class:`Module` this returns self.
        """
        if isinstance(self, ast.stmt):
            return cast(_typing.ASTstmt, self)
        if isinstance(self, ast.Module):
            return self
        return self.parent.statement
    
    @cached_property
    def _is_statement(self) -> bool:
        return isinstance(self, ast.stmt)
    
    def has_base(self, node:ast.AST) -> bool:
        """
        Check if this `ast.ClassDef` node inherits from the given type.

        :param node: The node defining the base to look for.
            Usually this is a :class:`Name` node.
        :type node: ASTNode
        """
        if not isinstance(self, ast.ClassDef):
            return False
        return bool(node in self.bases)
    
    def locate_child(self, child:'ASTNode', recurse:bool=False) -> Tuple[str, Union['_typing.ASTNode', Sequence['_typing.ASTNode']]]:
        """Find the field of this node that contains the given child.
        :param child: The child node to search fields for.
        :param recurse: Whether to recurse in all nested children to find the node.
        :type child: ASTNode
        :returns: A tuple of the name of the field that contains the child,
            and the sequence or node that contains the child node.
        :rtype: tuple(str, iterable(ASTNode) or ASTNode)
        :raises ValueError: If no field could be found that contains
            the given child.
        """
        for field in self._fields:
            node_or_sequence: Union['ASTNode', Sequence['ASTNode']] = getattr(self, field)
            # /!\ compiler.ast Nodes have an __iter__ walking over child nodes
            if child is node_or_sequence:
                return field, child
            if (
                isinstance(node_or_sequence, (tuple, list))
                and child in node_or_sequence
            ):
                return field, node_or_sequence
        
        if recurse and len(self.children)>0:
            for field in self._fields:
                _node_or_seq: Union['ASTNode', Sequence['ASTNode']] = getattr(self, field)
                for grand_child in _node_or_seq if isinstance(_node_or_seq, (tuple, list)) else [_node_or_seq]:
                    if not isinstance(grand_child, ASTNode):
                        continue
                    try:
                        return field, grand_child.locate_child(child, True)[1]
                    except ValueError:
                        pass
        
        msg = "Could not find %s in %s's children"
        raise ValueError(msg % (repr(child), repr(self)))

    def infer(self, context:'OptionalInferenceContext'=None) -> Iterator['_typing.ASTNode']:
        # workaround cyclic import
        from . import inference
        return inference.infer(self, context) #type:ignore[arg-type]
    
    @lru_cache()
    def literal_eval(self) -> Any:
        return ast.literal_eval(cast(ast.AST, self))

    # The MIT License (MIT)
    # Copyright (c) 2015 Read the Docs, Inc
    def resolve(self, basename: str) -> str:
        """
        Resolve a basename to get its fully qualified name in the context of self.

        :param self: The node representing the context in which to resolve the base name.
        :param basename: The partial base name to resolve.
        :returns: The fully resolved base name.
        """
        full_basename = basename

        top_level_name = re.sub(r"\(.*\)", "", basename).split(".", 1)[0]

        try:
            assigns = self.lookup(top_level_name)[1]
        except LookupError: # lookup() does not raise LookupError anymore, but maybe it should?
            assigns = []

        for assignment in assigns:
            if isinstance(assignment, ast.ImportFrom):
                import_name = get_full_import_name(assignment, top_level_name)
                full_basename = basename.replace(top_level_name, import_name, 1)
                break
            elif isinstance(assignment, ast.Import):
                import_name = resolve_import_alias(top_level_name, assignment.names)
                full_basename = basename.replace(top_level_name, import_name, 1)
                break
            elif isinstance(assignment, ast.ClassDef):
                full_basename = assignment.qname
                break
            elif isinstance(assignment, ast.Name) and is_assign_name(assignment):
                full_basename = "{}.{}".format(assignment.scope.qname, assignment.id)
                # TODO: handle aliases
            elif isinstance(assignment, ast.arg):
                full_basename = "{}.{}".format(assignment.scope.qname, assignment.arg)
        
        full_basename = re.sub(r"\(.*\)", "()", full_basename)

        # Some unecessary -yet- support for builtins:
        # if full_basename.startswith("builtins."):
        #     return full_basename[len("builtins.") :]

        # if full_basename.startswith("__builtin__."):
        #     return full_basename[len("__builtin__.") :]

        # dottedname = full_basename.split('.')
        # if dottedname[0] in self._parser.modules:
        #     origin_module = self._parser.modules[dottedname[0]]
        #     ...
        #     # TODO: finish me

        return full_basename

    def node_ancestors(self) -> Iterator["_typing.ASTNode"]:
        """Yield parent, grandparent, etc until there are no more."""
        parent = self.parent
        while parent is not None:
            yield parent
            parent = parent.parent
    
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
        linenumber = self.lineno
        if linenumber:
            linenumber += lineno_offset
        elif lineno_offset and self.parent is None:
            linenumber = lineno_offset
        else:
            linenumber = '???'

        warnings.warn(f'{description(self)}:{linenumber}: {descr}', category=exceptions.StaticAnalysisWarning)

    def parent_of(self, node: 'ASTNode') -> bool:
        """Check if this node is the parent of the given node.
        :param node: The node to check if it is the child.
        :type node: ASTNode
        :returns: True if this node is the parent of the given node,
            False otherwise.
        :rtype: bool
        """
        return any(self is parent for parent in node.node_ancestors())

    @cached_property
    def _is_from_decorator(self) -> bool:
        """Return True if the node is the child of a decorator"""

        for parent in self.node_ancestors():
            if isinstance(parent, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef)):
                field, _ = parent.locate_child(self, True)
                return field == 'decorator_list'
                
        return False
    
    @lru_cache()
    def unparse(self) -> str:
        return self._parser.unparse(self)

    @lru_cache()
    def lookup(self, name: str, offset:int=0) -> Tuple['_typing.ASTNode', List['_typing.ASTNode']]:
        """Lookup where the given variable is assigned.

        The lookup starts from self's scope. If self is not a frame itself
        and the name is found in the inner frame locals, statements will be
        filtered to remove ignorable statements according to self's location.

        :param name: The name of the variable to find assignments for.
        :param offset: The line offset to filter statements up to.

        :returns: The scope node and the list of assignments associated to the
            given name according to the scope node where it has been found.
        :returntype: tuple[ASTNode, List[_typing.LocalsAssignT]]
        """
        return _lookup.lookup(self, name, offset)
    
    def infer_name(self, name:str) -> Iterator['ASTNode']:
        # TODO
        return

class Context(enum.Enum):
    Load = 1
    Store = 2
    Del = 3

_CONTEXT_MAP = {
    ast.Load: Context.Load,
    ast.Store: Context.Store,
    ast.Del: Context.Del,
    ast.Param: Context.Store,
}

def is_assign_name(node: Union[ast.Name, ast.Attribute]) -> bool:
    """
    Whether this node is the target of an assigment.
    """
    return get_context(node) == Context.Store

def is_del_name(node: Union[ast.Name, ast.Attribute]) -> bool:
    """
    Whether this node is the target of a del statment.
    """
    return get_context(node) == Context.Del

@functools.lru_cache(maxsize=None)
def get_context(node: Union[ast.Attribute, ast.List, ast.Name, ast.Subscript, ast.Starred, ast.Tuple]) -> Context:
    """
    Wraps the context ast context classes into a more friendly enumeration.

    Dynamically created nodes do not have the ctx field, in this case fall back to Load context.
    """

    # Just in case, we use getattr because dynamically created nodes do not have the ctx field.
    try:
        return _CONTEXT_MAP[type(getattr(node, 'ctx', ast.Load()))] # type:ignore[index]
    except KeyError as e:
        raise ValueError(f"Can't get the context of {node!r}") from e

def is_frame_node(node: 'ASTNode') -> bool:
    """
    Whether this node is a frame.
    """
    return isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))

def is_scoped_node(node: 'ASTNode') -> bool:
    """
    Whether this node is a scope.
    """
    return isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef, ast.Module, 
                             ast.GeneratorExp, ast.DictComp, ast.SetComp, ast.ListComp, ast.Lambda))


def get_module_package(node: _typing.Module) -> Optional[_typing.Module]:
    """
    Returns the parent package of this module or `None` if not found. 

    Some code rely on the fact that `Module.parent` property is always None. 
    So we should not overide this behaviour.
    """
    parent_name = '.'.join(node.qname.split('.')[:-1])
    if not parent_name:
        # top-level module
        return None
    return node._parser.modules.get(parent_name)

# ==========================================================
# relative imports

# The MIT License (MIT)
# Copyright (c) 2015 Read the Docs, Inc
def get_full_import_name(import_from:ast.ImportFrom, name:str) -> str:
    """Get the full path of a name from a ``from x import y`` statement.
    :param import_from: The astroid node to resolve the name of.
    :param name:
    :returns: The full import path of the name.
    """
    partial_basename = resolve_import_alias(name, import_from.names)

    module_name = import_from.module
    if import_from.level:
        module_name = relative_to_absolute(import_from)

    return "{}.{}".format(module_name, partial_basename)

# The MIT License (MIT)
# Copyright (c) 2015 Read the Docs, Inc
def resolve_import_alias(name:str, import_names:Iterable[ast.alias]) -> str:
    """Resolve a name from an aliased import to its original name.
    :param name: The potentially aliased name to resolve.
    :param import_names: The pairs of original names and aliases
        from the import.
    :returns: The original name.
    """
    resolved_name = name

    for importname in import_names:
        import_name, imported_as = importname.name, importname.asname
        if import_name == name:
            break
        if imported_as == name:
            resolved_name = import_name
            break

    return resolved_name

def relative_to_absolute(node: ast.ImportFrom) -> str:
    """Convert a relative import path to an absolute one.

    Parameters:
        node: The "from ... import ..." AST node.
        name: The imported name.

    Returns:
        The absolute import path of the module this nodes imports from.
    """
    modname = node.module
    level = node.level
    
    if level:
        # Relative import.
        parent: Optional[_typing.Module] = cast(_typing.ASTNode, node).root
        if parent._is_package: #type:ignore[union-attr]
            level -= 1
        for _ in range(level):
            if parent is None:
                break
            parent = get_module_package(parent)
        if parent is None:
            cast(_typing.ASTNode, node)._parser._report(node,
                "relative import level (%d) too high" % node.level,
                )
            return
        if modname is None:
            modname = parent.qname
        else:
            modname = f'{parent.qname}.{modname}'
    else:
        # The module name can only be omitted on relative imports.
        assert modname is not None
    
    return modname

#   Copyright 2006-2008 Michael Hudson <mwh@python.net>
#   Copyright 2006-2020 Pydoctor contributors

@overload
def node2dottedname(node: Union[ast.Attribute, ast.Name]) -> List[str]: ...
@overload
def node2dottedname(node: Optional[ast.expr], strict:bool=False) -> Optional[List[str]]:...
def node2dottedname(node: Optional[ast.expr], strict:bool=False) -> Optional[List[str]]:
    """
    Resove expression composed by `ast.Attribute` and `ast.Name` nodes to a list of names. 
    :note: Supports variants `AssignAttr` and `AssignName`.
    :note: Strips the subscript slice, i.e. `Generic[T]` -> `Generic`, except if scrict=True.
    """
    parts = []
    if isinstance(node, ast.Subscript) and not strict:
        node = node.value
    while isinstance(node, (ast.Attribute)):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, (ast.Name)):
        parts.append(node.id)
    else:
        return None
    parts.reverse()
    return parts


@attr.s(auto_attribs=True)
class TypeInfo:
    """
    Optionnaly holds type information.
    """
    type_annotation: Optional[_typing.ASTexpr]
    classdef: Optional[_typing.ClassDef]

    def __bool__(self) -> bool:
        """
        Does this type info actually holds information?
        """
        return self.type_annotation is not None
    
    def __str__(self) -> str:
        """
        Type information as string.
        """
        return self.type_annotation.unparse() if self else '??'

class Instance:
    """
    This class is selectively added to the bases of the following ast nodes:
    `Constant`, `List`, `Tuple`, `Dict`, `Set`.

    :var type_info: The type information of this instance.
    """
    type_info: TypeInfo

    @classmethod
    def create_instance(cls, *args:Any, 
             classdef:Optional[ast.ClassDef]=None, 
             type_annotation:Optional[ast.expr]=None, 
             **kwargs:Any) -> 'Instance':
        """
        Special factory method to create instances of nodes that represent Instances. 

        It can be instanciated directly to represent any object.
        
        It's also used to create inferred 
        `ast.Constant`, `ast.List`, `ast.Tuple`, `ast.Dict` or `ast.Set` nodes.
        """
        i: Instance = cls(*args, **kwargs)
        i._init_type_info(classdef, type_annotation)
        return i
    
    def _init_type_info(self, classdef:Optional[ast.ClassDef]=None, 
                type_annotation:Optional[ast.expr]=None, ) -> None:
        self.type_info = self._get_type_info(classdef, type_annotation)

    def _get_type_info(self, classdef:Optional[_typing.ClassDef], type_annotation:Optional[ast.expr], ) -> TypeInfo:

        _type = None
        if type_annotation is not None:
            _type = type_annotation
        elif classdef is not None:
            _type = _astutils.qname_to_ast(classdef.qname)
        elif isinstance(self, ast.List):
            _type = _astutils.qname_to_ast("list")
        elif isinstance(self, ast.Set):
            _type = _astutils.qname_to_ast("set")
        elif isinstance(self, ast.Tuple):
            _type = _astutils.qname_to_ast("tuple")
        elif isinstance(self, ast.Dict):
            _type = _astutils.qname_to_ast("dict")
        elif isinstance(self, ast.Constant) and self.value is not ...:
            _type = _astutils.qname_to_ast(self.value.__class__.__name__)
        
        return TypeInfo(_type, classdef=classdef)
        
