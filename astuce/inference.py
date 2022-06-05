
"""
Core of the inference engine.
"""

import ast
import functools
import itertools
import sys
from typing import Any, Callable, Iterable, Iterator, Optional, List, Union
from . import _context, nodes, exceptions, _decorators
from . import _typing
from ._typing import ASTNode as ASTNodeT, _InferMethT
from ._context import OptionalInferenceContext, copy_context, InferenceContext
from ._astutils import fix_ast, literal_to_ast
from ._assigned_statements import assigned_stmts
from ._inference_decorators import path_wrapper, yes_if_nothing_inferred, raise_if_nothing_inferred

# An idea to improve support for builtins: https://stackoverflow.com/a/71969838

def _infer_stmts(
    stmts: List[ASTNodeT], 
    context: OptionalInferenceContext, 
    frame:Optional[ASTNodeT]=None) -> Iterator[ASTNodeT]:
    """Return an iterator on statements inferred by each statement in *stmts*."""
    if not stmts:
        return # empty list
    _parser = stmts[0]._parser 
    inferred = False
    if context is not None:
        context = copy_context(context)
    else:
        context = _parser._new_context()

    for stmt in stmts:
        if stmt is nodes.Uninferable:
            yield stmt
            inferred = True
            continue

        try:
            for inf in stmt.infer(context=context):
                yield inf
                inferred = True
        except exceptions.NameInferenceError:
            continue
        except exceptions.InferenceError:
            yield nodes.Uninferable
            inferred = True
    if not inferred:
        raise exceptions.InferenceError(
            "Inference failed for all members of {stmts!r}.",
            stmts=stmts,
            frame=frame,
            context=context,
        )

def infer(self:ASTNodeT, context:Optional[_context.InferenceContext]=None) -> Iterator[ASTNodeT]:
    """
    Get a generator of the inferred values. See `ASTNode.infer`.

    This is kinda the main entry point to the inference system. 

    :returns: The inferred values.
    :rtype: iterable
    """
    if not context:
        # nodes_inferred?
        yield from _infer(self, context=context)
        return

    if self in context.inferred:
        yield from context.inferred[self]
        return

    generator = _infer(self, context=context)
    results = []

    # Limit inference amount to help with performance issues with
    # exponentially exploding possible results.
    limit = self._parser.max_inferable_values
    for i, result in enumerate(generator):
        if i >= limit or (context.nodes_inferred > context.max_inferred):
            uninferable = nodes.Uninferable
            results.append(uninferable)
            yield uninferable
            break
        results.append(result)
        yield result
        context.nodes_inferred += 1

    # Cache generated results for subsequent inferences of the
    # same node.
    context.inferred[self] = tuple(results)
    return

def safe_infer(node, context=None):
    """Return the inferred value for the given node.

    Return None if inference failed or if there is some ambiguity (more than
    one node has been inferred).
    """
    try:
        inferit = node.infer(context=context)
        value = next(inferit)
    except (exceptions.InferenceError, StopIteration):
        return None
    try:
        next(inferit)
        return None  # None if there is ambiguity on the inferred node
    except exceptions.InferenceError:
        return None  # there is some kind of ambiguity
    except StopIteration:
        return value



class infer_load_name:
    """
    Code to infer a `ast.Name` instance with a ``Load`` context to possible values.
    
    :note: This is also used to infer augmented assigments.
    """

    @staticmethod
    def _higher_function_scope(node:ASTNodeT) -> Optional[ASTNodeT]:
        """Search for the first function which encloses the given
        scope. This can be used for looking up in that function's
        scope, in case looking up in a lower scope for a particular
        name fails.

        :param node: A scope node.
        :returns:
            ``None``, if no parent function scope was found,
            otherwise an instance of :class:`astroid.nodes.scoped_nodes.Function`,
            which encloses the given node.
        """
        current = node
        while current.parent and not isinstance(current.parent, ast.FunctionDef):
            current = current.parent
        if current and current.parent:
            return current.parent
        return None

    # Arguably the most important inference logic:
    @classmethod
    def infer_name(cls, self:_typing.Name, context:OptionalInferenceContext=None) -> Iterator[ASTNodeT]:
        """infer a Name: use name lookup rules"""
        frame, stmts = self.lookup(self.id)
        if not stmts:
            # Try to see if the name is enclosed in a nested function
            # and use the higher (first function) scope for searching.
            parent_function = cls._higher_function_scope(self.scope)
            if parent_function:
                _, stmts = parent_function.lookup(self.id)

            if not stmts:
                raise exceptions.NameInferenceError(
                    name=self.id, scope=self.scope, context=context
                )
        context = copy_context(context)
        return _infer_stmts(stmts, context, frame)

def _raise_no_infer_method(node:ASTNodeT, context: OptionalInferenceContext) -> Iterator[ASTNodeT]:
    """we don't know how to resolve a statement by default"""
    raise exceptions.InferenceError(
        "No inference function for node {nodetype!r}. Context: {context!r}", nodetype=node.__class__.__name__, context=context
    )

_globals = globals()
@functools.lru_cache()
def _get_infer_meth(node: ASTNodeT) -> _InferMethT:
    return _globals.get(f'_infer_{node.__class__.__name__}', _raise_no_infer_method)

def _infer_end(node:ASTNodeT, context: OptionalInferenceContext) -> Iterator[ASTNodeT]:
    """Inference's end for nodes that yield themselves on inference

    These are objects for which inference does not have any semantic,
    such as Module or Constants.
    """
    yield node

def _infer(node:ASTNodeT, context: OptionalInferenceContext) -> Iterator[ASTNodeT]:
    """
    Redirects to the right method to infer a node. 
    Equivalent to ast astroid's NodeNG._infer() method. 
    """
    return _get_infer_meth(node)(node, context)

def _infer_assign_name(node:ASTNodeT, context: OptionalInferenceContext) -> Iterator[ASTNodeT]:
    """
    From astroid's inference.infer_assign() function.
    """
    if isinstance(node.parent, ast.AugAssign):
        return node.parent.infer(context)

    stmts = list(assigned_stmts(node, context=context))
    return _infer_stmts(stmts, context)

@path_wrapper
@raise_if_nothing_inferred
def _infer_Name(node:ASTNodeT, context: OptionalInferenceContext) -> Iterator[ASTNodeT]:
    if nodes.is_assign_name(node):
        return _infer_assign_name(node, context)
    elif nodes.is_del_name(node):
        # TODO: Check what's the inference of a del name.
        assert False
        return
    else:
        return infer_load_name.infer_name(node, context)

@path_wrapper
@raise_if_nothing_inferred
def _infer_Attribute(node:ASTNodeT, context: OptionalInferenceContext) -> Iterator[ASTNodeT]:
    # We dont't support attribute inference right now.
    if nodes.is_assign_name(node):
        return
    elif nodes.is_del_name(node):
        return
    else:
        return #infer_load_name.infer_name(node, context)

# frame nodes infers to self, it's the end of the inference.
_infer_ClassDef = _infer_end
_infer_Lambda = _infer_end
_infer_FunctionDef = _infer_end
_infer_AsyncFunctionDef = _infer_end
_infer_Lambda = _infer_end

# constant nodes can't be inferred more ;-)
_infer_Constant = _infer_end

# not too sure why Slice nodes infers to self, but keeping the same logic as astroid here.
# Actually, the slice inference happens in the subscript handling.
_infer_Slice = _infer_end

@raise_if_nothing_inferred
def _infer_IfExp(node:_typing.IfExp, context: OptionalInferenceContext=None) -> Iterator[ASTNodeT]:
    """Support IfExp inference

    If we can't infer the truthiness of the condition, we default
    to inferring both branches. Otherwise, we infer either branch
    depending on the condition.
    """
    both_branches = False
    # We use two separate contexts for evaluating lhs and rhs because
    # evaluating lhs may leave some undesired entries in context.path
    # which may not let us infer right value of rhs.

    context = context or node._parser._new_context()
    lhs_context = copy_context(context)
    rhs_context = copy_context(context)
    try:
        test = next(node.test.infer(context=copy_context(context)))
    except (exceptions.InferenceError, StopIteration):
        both_branches = True
    else:
        if test is not nodes.Uninferable:
            if test.bool_value():
                yield from node.body.infer(context=lhs_context)
            else:
                yield from node.orelse.infer(context=rhs_context)
        else:
            both_branches = True
    if both_branches:
        yield from node.body.infer(context=lhs_context)
        yield from node.orelse.infer(context=rhs_context)

# for compatibility
@raise_if_nothing_inferred
def _infer_Index(self:ASTNodeT, context: OptionalInferenceContext=None) -> Iterator[ASTNodeT]:
    return self.value.infer(context)

def _infer_sequence_helper(node:Union[_typing.Tuple, _typing.List, _typing.Set], context: OptionalInferenceContext=None) -> List[ASTNodeT]:
    """Infer all values based on elts"""
    values = []

    for elt in node.elts:
        if isinstance(elt, ast.Starred):
            starred = safe_infer(elt.value, context)
            if not starred:
                raise exceptions.InferenceError("Ambiguious star expression: {node!r}", node=elt)
            if not hasattr(starred, "elts"):
                raise exceptions.InferenceError("Inferred star expression is not iterable: {node!r}", node=elt)
            values.extend(_infer_sequence_helper(starred))
        elif isinstance(elt, ast.NamedExpr):
            value = safe_infer(elt.value, context)
            if not value:
                raise exceptions.InferenceError(node=node, context=context)
            values.append(value)
        else:
            values.append(elt)
    return values


@raise_if_nothing_inferred
def infer_sequence(self:Union[_typing.Tuple, _typing.List, _typing.Set], context: OptionalInferenceContext=None) -> Iterator[ASTNodeT]:
    has_starred_named_expr = any(
        isinstance(e, (ast.Starred, ast.NamedExpr)) for e in self.elts
    )
    if has_starred_named_expr:
        values = _infer_sequence_helper(self, context)
        
        new_seq = type(self).create_instance(
            lineno=self.lineno, col_offset=self.col_offset, elts=values,
        )
        yield fix_ast(new_seq, self.parent)
    else:
        yield self

_infer_List = infer_sequence
_infer_Tuple = infer_sequence
_infer_Set = infer_sequence

_OPPERATORS = {
    
      # Unary operators
      ast.Not    : lambda o: not o,
      ast.Invert : lambda o: ~o,
      ast.UAdd   : lambda o: +o,
      ast.USub   : lambda o: -o,
      
      # Binary operators
      ast.Add    : lambda a, b: a + b,
      ast.Sub    : lambda a, b: a - b,
      ast.Mult   : lambda a, b: a * b,
      ast.Div    : lambda a, b: a / b,
      ast.Mod    : lambda a, b: a % b,
      ast.Pow    : lambda a, b: a**b,
      ast.LShift : lambda a, b: a << b,
      ast.RShift : lambda a, b: a >> b,
      ast.BitOr  : lambda a, b: a | b,
      ast.BitAnd : lambda a, b: a & b,
      ast.BitXor : lambda a, b: a ^ b,
      
      # Compare operators
      ast.Eq     : lambda a, b: a == b,
      ast.NotEq  : lambda a, b: a != b,
      ast.Lt     : lambda a, b: a < b,
      ast.LtE    : lambda a, b: a <= b,
      ast.Gt     : lambda a, b: a > b,
      ast.GtE    : lambda a, b: a >= b,

      ast.And    : lambda i,j: i and j,
      ast.Or     : lambda i,j: i or j,
      ast.Is     : lambda i,j: i is j,
    }

def _invoke_binop_inference(left: ASTNodeT, opnode: _typing.BinOp, op:ast.operator, right: ASTNodeT, context: OptionalInferenceContext) -> Iterator[ASTNodeT]:
    """
    Infer a binary operation between a left operand and a right operand.

    This is used by both normal binary operations and augmented binary
    operations.

    :note: left and right are inferred nodes.
    """

    operator_meth = _OPPERATORS[type(op)]
    try:
        literal_left = left.literal_eval()
        literal_right = right.literal_eval()
    except ValueError:
        # Unlike astroid, we can't infer binary operations on nodes that can't be evaluated as literals.
        yield nodes.Uninferable
        return
    try:
        inferred_literal = operator_meth(literal_left, literal_right)
    except Exception:
        # wrong types
        raise exceptions.InferenceError(node=opnode)

    yield fix_ast(literal_to_ast(inferred_literal), parent=opnode.parent)

@yes_if_nothing_inferred
@path_wrapper
def _infer_BinOp(self: _typing.BinOp, context: OptionalInferenceContext) -> Iterator[ASTNodeT]:
    """
    Binary operation inference logic.
    """
    left = self.left
    right = self.right

    # we use two separate contexts for evaluating lhs and rhs because
    # 1. evaluating lhs may leave some undesired entries in context.path
    #    which may not let us infer right value of rhs
    # TODO: Is this true for astuce? (this was part of astroid.)
    
    context = context or self._parser._new_context()
    lhs_context = copy_context(context)
    rhs_context = copy_context(context)
    lhs_iter = left.infer(context=lhs_context)
    rhs_iter = right.infer(context=rhs_context)
    for lhs, rhs in itertools.product(lhs_iter, rhs_iter):
        if any(value is nodes.Uninferable for value in (rhs, lhs)):
            # Don't know how to process this.
            yield nodes.Uninferable
            return

        yield from _invoke_binop_inference(lhs, self, self.op, rhs, context)

def _infer_lhs(node: ASTNodeT, context:InferenceContext) -> Iterator[ASTNodeT]:
    # won't work with a path wrapper
    """
    Infers the left hand side in augmented binary operations.

    @note: It only supports ast.Name instances at the moment.
    """
    if isinstance(node, ast.Name):
        yield from infer_load_name.infer_name(node, context)
    else:
        # TODO: we could support Attribute and Subscript nodes in the future
        yield nodes.Uninferable

@raise_if_nothing_inferred
@path_wrapper
def _infer_AugAssign(self:_typing.AugAssign, context: OptionalInferenceContext=None) -> Iterator[ASTNodeT]:
    """Inference logic for augmented binary operations."""
    context = context or self._parser._new_context()
    lhs_context = copy_context(context)
    rhs_context = copy_context(context)
    lhs_iter = list(_infer_lhs(self.target, context=lhs_context))
    rhs_iter = list(self.value.infer(context=rhs_context))
    print(f'_infer_AugAssign left: {lhs_iter}, right: {rhs_iter}', file=sys.stderr)

    for lhs, rhs in itertools.product(lhs_iter, rhs_iter):
        if any(value is nodes.Uninferable for value in (rhs, lhs)):
            # Don't know how to process this.
            yield nodes.Uninferable
            return
        

        yield from _invoke_binop_inference(lhs, self, self.op, rhs, rhs_context)
        
# Defers to self.value.infer()
def _infer_Expr(self:_typing.Expr, context: OptionalInferenceContext=None) -> Iterator[ASTNodeT]:
    return self.value.infer(context=context)

def _infer_Subscript(self:_typing.Subscript, context: OptionalInferenceContext=None) -> Iterator[ASTNodeT]:
    return
    # TODO
