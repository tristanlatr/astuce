"""
These classes are for type annotations only, do not instanciate them.
"""

from typing import TYPE_CHECKING, Callable, Iterator, NewType, Union, Type
import ast

if TYPE_CHECKING:
    from .nodes import ASTNode as ConcreteASTNode, Instance, Uninferable
    from ._context import OptionalInferenceContext
    class ConcreteInstance(ConcreteASTNode, Instance):
        ...
    UninferableT = Type[Uninferable]
else:
    ConcreteASTNode = object
    ConcreteInstance = object
    OptionalInferenceContext = object
    Uninferable = object
    UninferableT = Type[object]

class Module(ast.Module, ConcreteASTNode):...
class ClassDef(ast.ClassDef, ConcreteASTNode):...
class FunctionDef(ast.FunctionDef, ConcreteASTNode):...
class AsyncFunctionDef(ast.AsyncFunctionDef, ConcreteASTNode):...
class Name(ast.Name, ConcreteASTNode):...
class Attribute(ast.Attribute, ConcreteASTNode):...
class arg(ast.arg, ConcreteASTNode):...
class Import(ast.Import, ConcreteASTNode):...
class ImportFrom(ast.ImportFrom, ConcreteASTNode):...
class GeneratorExp(ast.GeneratorExp, ConcreteASTNode):...
class DictComp(ast.DictComp, ConcreteASTNode):...
class SetComp(ast.DictComp, ConcreteASTNode):...
class ListComp(ast.ListComp, ConcreteASTNode):...
class Lambda(ast.Lambda, ConcreteASTNode):...
class IfExp(ast.IfExp, ConcreteASTNode):...
class For(ast.For, ConcreteASTNode):...
class AsyncFor(ast.AsyncFor, ConcreteASTNode):...
class Assign(ast.Assign, ConcreteASTNode):...
class AnnAssign(ast.AnnAssign, ConcreteASTNode):...
class AugAssign(ast.AugAssign, ConcreteASTNode):...
class BinOp(ast.BinOp, ConcreteASTNode):...
class Expr(ast.Expr, ConcreteASTNode):...
class Subscript(ast.Subscript, ConcreteASTNode):...
class alias(ast.alias, ConcreteASTNode):...

class List(ast.List, ConcreteInstance):...
class Tuple(ast.Tuple, ConcreteInstance):...
class Set(ast.Set, ConcreteInstance):...
class Dict(ast.Dict, ConcreteInstance):...
class Constant(ast.Constant, ConcreteInstance):... # type:ignore[misc]

comprehension = Union[GeneratorExp, DictComp, SetComp, ListComp]


LocalsAssignT = Union[ClassDef,
            FunctionDef, AsyncFunctionDef, 
            Name, arg, alias]
"""
This type represent all possible types stored in scopes locals dict.
"""

FrameNodeT = Union[Module, FunctionDef, AsyncFunctionDef, ClassDef, Lambda]
ScopedNodeT = Union[Module, FunctionDef, AsyncFunctionDef, ClassDef, Lambda, 
                GeneratorExp, DictComp, SetComp, ListComp]


if TYPE_CHECKING:
    class ASTstmt(ConcreteASTNode, ast.stmt):... # type:ignore[misc]
    class ASTexpr(ConcreteASTNode, ast.stmt):... # type:ignore[misc]
    class ASTNode(ast.AST, ConcreteASTNode):...
else:
    ASTstmt = ast.stmt
    ASTexpr = ast.expr
    ASTNode = ast.AST

InferResult = Iterator[Union[ASTNode, Uninferable]]
_InferMethT = Callable[[ASTNode, OptionalInferenceContext], InferResult]

