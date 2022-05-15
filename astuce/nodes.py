import builtins
import enum
from functools import lru_cache
from typing import Any, Callable, Dict, Iterator, Optional, Sequence, List, Tuple, Type, Union, cast, TYPE_CHECKING
import sys
import ast
from ast import AST

# TODO: remove once Python 3.7 support is dropped
if sys.version_info < (3, 8):
    from cached_property import cached_property
else:
    from functools import cached_property  # noqa: WPS440

from .exceptions import LastNodeError, RootNodeError
from . import _typing

if TYPE_CHECKING:
    from .parser import Parser

_builtins_names = dir(builtins)

class ASTNode:
    """This class is dynamically added to the bases of each AST node class.
    
    :var lineno: 
        - Modules lineno -> 0
        - Missing lineno information -> -1 (should not happend)

    """

    parent: 'ASTNode' = None # type:ignore
    
    _locals: Dict[str, List[_typing.LocalsAssignT]] = None # type:ignore
    _parser: 'Parser' = None # type:ignore
    _modname: Optional[str] = None
    _is_package: bool = False
    
    @cached_property
    def lineno(self) -> int:
        if isinstance(self, ast.Module):
            return 0
        return getattr(self, 'lineno', -1)

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
    
    def _set_local(self, name:str, node:'ast.AST') -> None:
        """Define that the given name is declared in the given statement node.

        .. seealso:: `scope`

        :param name: The name that is being defined.
        :type name: str

        :param node: The node that defines the given name (i.e ast.Name objects).
        :type node: ASTNode
        """
        if isinstance(self, ast.NamedExpr):
            return self.frame._set_local(name, node)
        if not is_frame_node(self):
            return self.parent._set_local(name, node)

        # nodes that can be stored in the locals dict
        LOCALS_ASSIGN_NAME_NODES = (ast.ClassDef, 
                                    ast.FunctionDef, 
                                    ast.AsyncFunctionDef, 
                                    ast.Name, 
                                    ast.arg, 
                                    ast.Import, 
                                    ast.ImportFrom) 
            # ast.Attribute not supported at the moment, 
            # analysing assigments outside out the scope needs more work.
        
        assert isinstance(node, LOCALS_ASSIGN_NAME_NODES), f"cannot set {node} as local"
        assert not node in self.locals.get(name, ()), (self, node)
        self.locals.setdefault(name, []).append(node) # type:ignore[arg-type]

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
    def children(self) -> Sequence['ASTNode']:
        """Build and return the children of this node.

        Returns:
            A list of children.
        """
        children = []
        for field_name in cast(ast.AST, self)._fields:
            try:
                field = getattr(self, field_name)
            except AttributeError:
                continue
            if isinstance(field, ASTNode):
                field.parent = self
                children.append(field)
            elif isinstance(field, list):
                for child in field:
                    if isinstance(child, ASTNode):
                        child.parent = self
                        children.append(child)
        return children

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
    def previous_siblings(self) -> Sequence['ASTNode']:
        """Return the previous siblings of this node, starting from the closest.

        Returns:
            The previous siblings.
        """
        if self.position == 0:
            return []
        return self.parent.children[self.position - 1 :: -1]

    @cached_property
    def next_siblings(self) -> Sequence['ASTNode']:
        """Return the next siblings of this node, starting from the closest.

        Returns:
            The next siblings.
        """
        if self.position == len(self.parent.children) - 1:
            return []
        return self.parent.children[self.position + 1 :]

    @cached_property
    def siblings(self) -> Sequence['ASTNode']:
        """Return the siblings of this node.

        Returns:
            The siblings.
        """
        return [*reversed(self.previous_siblings), *self.next_siblings]

    @cached_property
    def previous(self) -> 'ASTNode':
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
    def next(self) -> 'ASTNode':  # noqa: A003
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
    def first_child(self) -> 'ASTNode':
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
    def last_child(self) -> 'ASTNode':  # noqa: A003
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
            assert isinstance(self, ASTNode)
            return self
        
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
    
    def has_base(self, node:'ASTNode') -> bool:
        """
        Check if this `ast.ClassDef` node inherits from the given type.

        :param node: The node defining the base to look for.
            Usually this is a :class:`Name` node.
        :type node: ASTNode
        """
        if not isinstance(self, ast.ClassDef):
            return False
        return bool(node in self.bases)
    
    def locate_child(self, child:'ASTNode', recurse:bool=False) -> Tuple[str, Union['ASTNode', Sequence['ASTNode']]]:
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

    def resolve(self, name:str) -> str:
        ...
        # TODO: adjust code from astroid to provide lookup() method. 
        # Then use this lookup() method here to provide name resolving. 

    def node_ancestors(self) -> Iterator["ASTNode"]:
        """Yield parent, grandparent, etc until there are no more."""
        parent = self.parent
        while parent is not None:
            yield parent
            parent = parent.parent

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
    def lookup(self, name: str, offset:int=0) -> Tuple['ASTNode', List['ASTNode']]:
        """Lookup where the given variable is assigned.

        The lookup starts from self's scope. If self is not a frame itself
        and the name is found in the inner frame locals, statements will be
        filtered to remove ignorable statements according to self's location.

        :param name: The name of the variable to find assignments for.
        :param offset: The line offset to filter statements up to.

        :returns: The scope node and the list of assignments associated to the
            given name according to the scope node where it has been found (locals,
            globals or builtin).
        """
        if is_scoped_node(self):
            return self._scope_lookup(self, name, offset=offset)
        return self.scope._scope_lookup(self, name, offset=offset)

    # TODO: Move the lookup logic into it's own module.
    def _scope_lookup(self, node: 'ASTNode', name:str, offset:int=0) -> Tuple['ASTNode', List['ASTNode']]:
        if isinstance(self, ast.Module):
            return self._module_lookup(node, name, offset)
        elif isinstance(self, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._function_lookup(node, name, offset)
        elif isinstance(self, ast.ClassDef):
            return self._class_lookup(node, name, offset)
        else:
            return self._base_scope_lookup(node, name, offset)
    
    def _module_lookup(self, node: 'ASTNode', name:str, offset:int=0) -> Tuple['ASTNode', List['ASTNode']]:
        # TODO: Handle {"__name__", "__doc__", "__file__", "__path__", "__package__"}
        """The names of module attributes available through the global scope."""

        return self._base_scope_lookup(node, name, offset)

    def _class_lookup(self, node: 'ASTNode', name:str, offset:int=0) -> Tuple['ASTNode', List['ASTNode']]:
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
            any(node == base or cast(ASTNode, base).parent_of(node) for base in self.bases)
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

            frame = self.parent.frame
            # line offset to avoid that class A(A) resolve the ancestor to
            # the defined class
            offset = -1
        else:
            frame = self
        return frame._base_scope_lookup(node, name, offset)

    def _function_lookup(self, node: 'ASTNode', name:str, offset:int=0) -> Tuple['ASTNode', List['ASTNode']]:
        assert isinstance(self, (ast.FunctionDef, ast.AsyncFunctionDef))
        
        if name == "__class__":
            # __class__ is an implicit closure reference created by the compiler
            # if any methods in a class body refer to either __class__ or super.
            # In our case, we want to be able to look it up in the current scope
            # when `__class__` is being used.
            frame = self.parent.frame
            if isinstance(frame, ast.ClassDef):
                return self, [frame]

        if node in self.args.defaults or node in self.args.kw_defaults:
            frame = self.parent.frame
            # line offset to avoid that def func(f=func) resolve the default
            # value to the defined function
            offset = -1
        else:
            # check this is not used in function decorators
            frame = self
        return frame._base_scope_lookup(node, name, offset)

    def _base_scope_lookup(self, node: 'ASTNode', name:str, offset:int=0) -> Tuple['ASTNode', List['ASTNode']]:
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
                return pscope._scope_lookup(node, name)
            pscope = pscope.parent and pscope.parent.scope

        # self is at the top level of a module, or is enclosed only by ClassDefs
        raise LookupError()
        # return builtin_lookup(name)
    
    # def nodes_of_class(
    #     self,
    #     klass: Union[Type[ast.AST], Tuple[Type[ast.AST], ...]],
    #     skip_klass: Optional[Union[Type[ast.AST], Tuple[Type[ast.AST], ...]]] = None,
    # ) -> Iterator['ASTNode']:
    #     """Get the nodes (including this one or below) of the given types.

    #     :param klass: The types of node to search for.

    #     :param skip_klass: The types of node to ignore. This is useful to ignore
    #         subclasses of :attr:`klass`.

    #     :returns: The node of the given types.
    #     """
    #     if isinstance(self, klass):
    #         yield self

    #     if skip_klass is None:
    #         for child_node in self.children:
    #             yield from child_node.nodes_of_class(klass, skip_klass)

    #         return

    #     for child_node in self.children:
    #         if isinstance(child_node, skip_klass):
    #             continue
    #         yield from child_node.nodes_of_class(klass, skip_klass)

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

def get_context(node: Union[ast.Attribute, ast.List, ast.Name, ast.Subscript, ast.Starred, ast.Tuple]) -> Context:
    """
    Wraps the context ast context classes into a more friendly enumeration.
    """
    return _CONTEXT_MAP[type(node.ctx)]

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
