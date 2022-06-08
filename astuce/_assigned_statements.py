"""
This module contains the code adjusted from astroid to infer/unpack assigned names from statements. 

Meaning understanding stuff like::

    a,b,(c,d) = 1,2,[3,4]
"""

from __future__ import annotations

import ast
from functools import lru_cache
import sys
from typing import Callable, Iterator, Optional, List, Any, Union

from .import nodes, exceptions
from .import _typing
from ._typing import ASTNode as ASTNodeT, Name as ASTNameT, InferResult
from ._context import OptionalInferenceContext, copy_context, InferenceContext
from ._inference_decorators import path_wrapper, yes_if_nothing_inferred, raise_if_nothing_inferred


AssignedStmtsPossibleNode = Union[_typing.List, _typing.Tuple, _typing.Name, _typing.Attribute, None]
# -- the following expression can appear in assignment context
#          | Attribute(expr value, identifier attr, expr_context ctx)
#          | Subscript(expr value, expr slice, expr_context ctx)
#          | Starred(expr value, expr_context ctx) # not supported 
#          | Name(identifier id, expr_context ctx)
#          | List(expr* elts, expr_context ctx)
#          | Tuple(expr* elts, expr_context ctx)
# TODO: Why None?

AssignedStmtsCall = Callable[
    [
        ASTNodeT,
        AssignedStmtsPossibleNode,
        Optional[InferenceContext],
        Optional[List[int]],
    ],
    Iterator[ASTNodeT],
]


@raise_if_nothing_inferred
def for_assigned_stmts(
    self: Union[_typing.For, _typing.AsyncFor],
    node: AssignedStmtsPossibleNode = None,
    context: InferenceContext | None = None,
    assign_path: list[int] | None = None,
) -> Any:
    if isinstance(self, ast.AsyncFor):
        # Skip inferring of async code
        # raise StopIteration
        return dict(node=self, unknown=node, assign_path=assign_path, context=context)
    if assign_path is None:
        for lst in self.iter.infer(context):
            if isinstance(lst, (ast.Tuple, ast.List)):
                yield from lst.elts
    else:
        # Unlike astroid, we don't support unpacking values in for assign statements
        yield nodes.Uninferable
    # raise StopIteration
    return dict(node=self, unknown=node, assign_path=assign_path, context=context)


def sequence_assigned_stmts(
    self: _typing.Tuple | _typing.List,
    node: AssignedStmtsPossibleNode = None,
    context: InferenceContext | None = None,
    assign_path: list[int] | None = None,
) -> Any:
    if assign_path is None:
        assign_path = []
    try:
        index = self.elts.index(node)
    except ValueError as exc:
        raise exceptions.InferenceError(
            "Tried to retrieve a node {node!r} which does not exist in {seq}",
            node=node,
            assign_path=assign_path,
            context=context,
            seq=ast.dump(self),
        ) from exc

    assign_path.insert(0, index)
    return assigned_stmts(self.parent,
        node=self, context=context, assign_path=assign_path
    )

def assend_assigned_stmts(
    self: _typing.Name | _typing.Attribute,
    node: AssignedStmtsPossibleNode = None,
    context: InferenceContext | None = None,
    assign_path: list[int] | None = None,
) -> Any:
    # if nodes.is_assign_name(self):
    # node=self here is important
    return assigned_stmts(self.parent, node=self, context=context)
    

@raise_if_nothing_inferred
def assign_assigned_stmts(
    self: _typing.AugAssign | _typing.Assign | _typing.AnnAssign,
    node: AssignedStmtsPossibleNode = None,
    context: InferenceContext | None = None,
    assign_path: list[int] | None = None,
) -> Any:
    if not assign_path:
        yield self.value
        return None
    yield from _wrap_resolve_assignment_parts(
        self.value, assign_path, context
    )
    # StopIteration
    return dict(node=self, unknown=node, assign_path=assign_path, context=context)

def _wrap_resolve_assignment_parts(node:_typing.ASTNode, assign_path: list[int], context:OptionalInferenceContext) -> Any:
    # This is needed because List.infer() infers all elements by default, but for resolving assigments,
    # we should not try to infer names in the list...
    # Lists inference infers elements by default, which we don't want in assigment context,
    # but inference as a whole is a semi-recursive operation, which can be applied several times,
    # this is why we need this recursive function. 
    
    # So there is this 'assign_context=True' option that provides the appropriate behaviour.
    if isinstance(node, (ast.List, ast.Tuple)):
        from astuce import inference
        yield from _resolve_assignment_parts(
            inference.infer_sequence(node, context=context, assign_context=True), 
            assign_path, context
        )
    else:
        yield from _resolve_assignment_parts(
            node.infer(context=context), 
            assign_path, context
        )

def assign_annassigned_stmts(
    self: _typing.AnnAssign,
    node: AssignedStmtsPossibleNode = None,
    context: InferenceContext | None = None,
    assign_path: list[int] | None = None,
) -> Any:
    for inferred in assign_assigned_stmts(self, node, context, assign_path):
        if inferred is None:
            yield nodes.Uninferable
        else:
            yield inferred

def _resolve_assignment_parts(parts:InferResult, assign_path: list[int], context:OptionalInferenceContext):
    # From astroid's protocols._resolve_assignment_parts()
    """
    :param parts: Inferred values for a given assigment.

    recursive function to infer multiple assignments, currently supports List and Tuple only.
    """
    assign_path = assign_path[:]
    index = assign_path.pop(0)
    for part in parts:
        assigned:Optional[ASTNodeT] = None
        if isinstance(part, (ast.Tuple, ast.List)):
            try:
                assigned = part.elts[index]
            except IndexError:
                return

        if not assigned:
            return

        if not assign_path:
            # we achieved to resolved the assignment path, don't infer the
            # last part
            yield assigned
        elif assigned is nodes.Uninferable:
            return
        else:
            # we are not yet on the last part of the path search on each
            # possibly inferred value
            try:
                yield from _wrap_resolve_assignment_parts(
                    assigned, assign_path, context
                )
            except exceptions.InferenceError as e:
                assigned._report(str(e))
                return

def _raise_no_assigned_stmts_method(self:ASTNodeT, _:ASTNodeT, context: OptionalInferenceContext, __:Any,) -> Iterator[ASTNodeT]:
    raise exceptions.InferenceError( # Typically ast.Starred nodes.
        "Node {node!r} is currently not supported by assigned_stmts().", node=self, context=context
    )
_globals = globals()
@lru_cache()
def _get_assigned_stmts_meth(node: ASTNodeT) -> AssignedStmtsCall:
    return _globals.get(f'_assigned_stmts_{node.__class__.__name__}', _raise_no_assigned_stmts_method)

def assigned_stmts(
    self: ASTNodeT,
    node: AssignedStmtsPossibleNode = None,
    context: OptionalInferenceContext = None,
    assign_path: list[int] | None = None,) -> InferResult:
    """
    Equivalent to astroid's NodeNG.assigned_stmts() method. 
    """
    return _get_assigned_stmts_meth(self)(self, node, context, assign_path)

_assigned_stmts_For = for_assigned_stmts
_assigned_stmts_Tuple = sequence_assigned_stmts
_assigned_stmts_List = sequence_assigned_stmts
_assigned_stmts_Name = assend_assigned_stmts
_assigned_stmts_Attribute = assend_assigned_stmts
_assigned_stmts_AugAssign = assign_assigned_stmts
_assigned_stmts_Assign = assign_assigned_stmts
_assigned_stmts_AnnAssign = assign_annassigned_stmts
