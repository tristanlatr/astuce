
"""
Core of the inference engine.
"""

import ast
import contextlib
import functools
import itertools
import sys
from typing import Any, Callable, Iterable, Iterator, Optional, List, Type, Union, cast
from . import _context, nodes, exceptions, _decorators
from . import _typing
from ._typing import ASTNode as ASTNodeT, _InferMethT, InferResult, UninferableT
from .nodes import fix_ast, literal_to_ast
from ._context import OptionalInferenceContext, copy_context, InferenceContext
from ._assigned_statements import assigned_stmts
from ._inference_decorators import path_wrapper, yes_if_nothing_inferred, raise_if_nothing_inferred

# An idea to improve support for builtins: https://stackoverflow.com/a/71969838

def _infer_stmts(
    stmts: List[Union[ASTNodeT, UninferableT]], 
    context: InferenceContext, 
    frame:Optional[ASTNodeT]=None) -> InferResult:
    """Return an iterator on statements inferred by each statement in *stmts*."""
    if not stmts:
        return # empty list

    inferred = False
    context = copy_context(context)

    for stmt in stmts:
        # Yields Uninferables as is
        if stmt is nodes.Uninferable:
            yield stmt
            inferred = True
            continue

        try:
            for inf in stmt.infer(context=context):
                yield inf
                inferred = True
        except exceptions.NameInferenceError as e:
            # TODO: Why are we ignoring the name errors here?
            stmt._report(f"NameInferenceError in _infer_stmts: {e}")
            continue
        except exceptions.InferenceError as e:
            stmt._report(f"InferenceError in _infer_stmts: {e}")
            yield nodes.Uninferable
            inferred = True
    if not inferred:
        raise exceptions.InferenceError(
            "Inference failed for all members of {stmts!r}.",
            stmts=stmts,
            frame=frame,
            context=context,
        )

def infer(self:ASTNodeT, context: OptionalInferenceContext=None) -> InferResult:
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
            self._report(f"Too many inference results")
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

def safe_infer(node: ASTNodeT, context: OptionalInferenceContext=None) -> Optional[ASTNodeT]:
    """Return the inferred value for the given node.

    Return None if inference failed, it's Uninfereable or if there is some ambiguity (more than
    one node has been inferred).
    """
    try:
        inferit = infer(node, context=context)
        value = next(inferit)
    except (exceptions.InferenceError, StopIteration):
        return None
    try:
        next(inferit)
        node._report(f"Inference is not safe")
        return None  # None if there is ambiguity on the inferred node
    except exceptions.InferenceError as e:
        # there is some kind of ambiguity and the second possible value failed to infer
        node._report(f"Inference is not safe (and failed): {e}")
        return None
    except StopIteration:
        # Since each elements of the list is inferred when inferring a list
        # uninferable value is inserted when we know there is a value but we can't
        # figure out informations about it. But for the sake of safe_infer() we 
        # filter these kind of sequences.
        if isinstance(value, (ast.Set, ast.Tuple, ast.List)):
            if any(ele is nodes.Uninferable for ele in value.elts):
                return None
        elif value is nodes.Uninferable:
            return None
        return value

# TODO: Do we really need this? Since the name inference is recursive by default and we infer list elements.
# @raise_if_nothing_inferred
# def recursively_infer(node:ASTNodeT, context:OptionalInferenceContext=None) -> InferResult:
#     # From the unpack_infer() function in astroid, except in our case we do not yield inferred elements when the node is a List or Tuple,
#     # we return the inferred list/tuple, which is the excepted behaviour imo. This is also why the function is
#     # named differently in astuce, because it's not designed the same way.
#     """
#     Recursively yield nodes inferred by the given node until the 
#     node infers to self or we reached the Uninferable result.
#     """
#     # if inferred is a final node, return it and stop
#     inferred = next(node.infer(context), nodes.Uninferable)
#     if inferred is node:
#         yield inferred
#         return dict(node=node, context=context)
#     # else, infer recursively, except Uninferable object that should be returned as is
#     for inferred in node.infer(context):
#         if inferred is nodes.Uninferable:
#             yield inferred
#         else:
#             yield from recursively_infer(inferred, context)
#     return dict(node=node, context=context)

def get_submodule(pack:_typing.Module, name:str, *, context:OptionalInferenceContext=None) -> Optional[ASTNodeT]:
    try:
        return pack._parser.modules[f"{pack._modname}.{name}"]
    except KeyError:
        return None

def _get_end_of_frame_sentinel(frame_node:_typing.FrameNodeT) -> _typing.ASTstmt:
    # we use a sentinel node when doing lookups with get_attr to void this behaviour:
    # https://github.com/PyCQA/astroid/pull/1612#issuecomment-1152741042

    assert nodes.is_frame_node(frame_node)
    
    if isinstance(frame_node, ast.Lambda):
        return frame_node
    
    # The last element in frame nodes should be the inserted sentinel "end of" node.
    if _is_end_of_frame_sentinel(frame_node.body[-1]):
        return frame_node.body[-1]
    else:
        raise exceptions.MissingSentinelNode(node=frame_node)

def _is_end_of_frame_sentinel(node:_typing.ASTNode) -> bool:
    if not isinstance(node, ast.Expr):
        return False
    try:
        v = node.value.literal_eval()
    except ValueError:
        return False
    else:
        if v == nodes._END_OF_FRAME_SENTINEL_CONSTANT:
            return True
    
    return False

def get_attr(ctx: _typing.FrameNodeT, name:str, *, ignore_locals:bool=False, context:OptionalInferenceContext=None) -> List[ASTNodeT]:
    """
    Get local attributes definitions matching the name from this frame node.
    """
    # TODO: Handle {"__name__", "__doc__", "__file__", "__path__", "__package__"}
    # TODO: Handle __class__, __module__, __qualname__,

    # Adjusted from astroid NodeNG.getattr() method, with minimal support for packages.
    
    if not name:
        raise exceptions.AttributeInferenceError(target=ctx, attribute=name, context=context)
    
    assert nodes.is_frame_node(ctx), "use get_attr() only on frame nodes"
    
    # values = ctx.lookup(name)[1] if not ignore_locals else []
    if not ignore_locals:
        values = _get_end_of_frame_sentinel(ctx).lookup(name)[1]
    else: 
        values = []

    if not values and isinstance(ctx, ast.Module) and ctx._is_package:
       # Support for sub-packages.
       sub = get_submodule(ctx, name, context=context)
       if sub:
           return [sub]
    
    # filter Del statements
    values = [n for n in values if not (isinstance(n, ast.Name) and nodes.is_del_name(n))]

    # If an AnnAssign with None value gets here it means that the variable is potentially unbound. TODO: is this true?
    
    def empty_annassign(value: _typing.ASTNode) -> bool:
        if isinstance(value, ast.Name) and nodes.is_assign_name(value):
            stmt = value.statement
            if isinstance(stmt, ast.AnnAssign) and stmt.value is None:
                return True
        return False
    
    # filter empty AnnAssigns statements, which are not attributes in the purest sense.
    values = [n for n in values if not empty_annassign(n)]
        
    if values:
        return values

    raise exceptions.AttributeInferenceError(target=ctx, attribute=name, context=context)

def infer_attr(ctx: ASTNodeT, name:str, *, context:OptionalInferenceContext=None) -> InferResult:
    # Adjusted from astroid NodeNG.igetattr() method.
    # But this function cannot infer instance attributes at this time.
    """
    Infer the possible values of the given variable.

    :param name: The name of the variable to infer.
    :type name: str

    :returns: The inferred possible values.
    """

    context = copy_context(context) if context else ctx._parser._new_context()

    try:
        yield from _infer_stmts(get_attr(ctx, name, context=context), context, frame=ctx)
    except exceptions.AttributeInferenceError as error:
        raise exceptions.InferenceError(
            str(error), target=ctx, attribute=name, context=context
            ) from error

#### Inference functions:


# Arguably the most important inference logic:
# :note: This is also used to infer the left side of augmented assigments.
def _infer_name(self:ast.Name, context:OptionalInferenceContext=None) -> InferResult:
    """
    Infer a Name: use name lookup rules.
    """
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

    self = cast(_typing.Name, self)
    frame, stmts = self.lookup(self.id)
    if not stmts:
        # Try to see if the name is enclosed in a nested function
        # and use the higher (first function) scope for searching.
        parent_function = _higher_function_scope(self.scope)
        if parent_function:
            _, stmts = parent_function.lookup(self.id)

        if not stmts:
            raise exceptions.NameInferenceError(
                name=self.id, scope=self.scope, context=context
            )
    context = copy_context(context)
    return _infer_stmts(stmts, context, frame)

def _raise_no_infer_method(node:ASTNodeT, context: OptionalInferenceContext) -> InferResult:
    """we don't know how to resolve a statement by default"""
    raise exceptions.InferenceError(
        "No inference function for node {nodetype!r}.", nodetype=node.__class__.__name__, context=context
    )

_globals = globals()
@functools.lru_cache()
def _get_infer_meth(node: ASTNodeT) -> _InferMethT:
    return _globals.get(f'_infer_{node.__class__.__name__}', _raise_no_infer_method)

def _infer_end(node:ASTNodeT, context: OptionalInferenceContext) -> InferResult:
    """Inference's end for nodes that yield themselves on inference

    These are objects for which inference does not have any semantic,
    such as Module or Constants.
    """
    yield node

def _infer(node:ASTNodeT, context: OptionalInferenceContext) -> InferResult:
    """
    Redirects to the right method to infer a node. 
    Equivalent to ast astroid's NodeNG._infer() method. 
    """
    return _get_infer_meth(node)(node, context)

def _infer_assign_name(node:ASTNodeT, context: OptionalInferenceContext) -> InferResult:
    """
    From astroid's inference.infer_assign() function.
    """
    if isinstance(node.parent, ast.AugAssign):
        return node.parent.infer(context)

    stmts = list(assigned_stmts(node, context=context))
    return _infer_stmts(stmts, context)

@path_wrapper
@raise_if_nothing_inferred
def _infer_Name(node:_typing.Name, context: OptionalInferenceContext) -> InferResult:
    if nodes.is_assign_name(node):
        return _infer_assign_name(node, context)
    elif nodes.is_del_name(node):
        # TODO: Check what's the inference of a del name.
        assert False
    else:
        return _infer_name(node, context)

@path_wrapper
@raise_if_nothing_inferred
def _infer_Attribute(node:_typing.Attribute, context: OptionalInferenceContext) -> InferResult:

    for owner in node.value.infer(context):
        if owner is nodes.Uninferable:
            node._report(f"Uninferable attribute left side: {node.value}")

            yield owner
            continue

        context = copy_context(context, node._parser._inference_cache)
        yield from infer_attr(owner, node.attr, context=context)
        
    return dict(node=node, context=context)

# frame nodes infers to self, it's the end of the inference.
_infer_Module = _infer_end
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
def _infer_IfExp(node:_typing.IfExp, context: OptionalInferenceContext=None) -> InferResult:
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
            try:
                inferred_literal = test.literal_eval()
            except ValueError:
                both_branches = True
            else:
                if bool(inferred_literal):
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
def _infer_Index(self:ASTNodeT, context: OptionalInferenceContext=None) -> InferResult:
    return self.value.infer(context)

def _infer_sequence_helper(node:Union[_typing.Tuple, _typing.List, _typing.Set], 
                           context: OptionalInferenceContext=None, 
                           infer_all_elements:bool=True) -> List[ASTNodeT]:
    """
    Infer all values based on elts. 
    
    If infer_all_elements is False, will only infer Starred and NamedExpr inside the list, this is used for tuple assignments.
    """
    values = []

    for i, elt in enumerate(node.elts):
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
            if infer_all_elements:
                # This part might change is the future, astroid behaved differently for some reason
                # TODO: Create an issue to gather more informations about this.
                
                value = safe_infer(elt, context)
                if value is None:
                    node._report(f"Sequence element ({i}) is not inferable")
                    value = nodes.Uninferable
                
                values.append(value)
            else:
                values.append(elt)
    return values


@raise_if_nothing_inferred
def _infer_sequence(self:Union[_typing.Tuple, _typing.List, _typing.Set], context: OptionalInferenceContext=None, assign_context:bool=False) -> InferResult:

    # avoids cyclic inferences on lists by checking if the node has Starred or NamedExpr nodes, 
    # but that's only applicable if we're in an assigment context, otherwise always infer all values of the list.
    
    has_starred_named_expr = any(
        isinstance(e, (ast.Starred, ast.NamedExpr)) for e in self.elts
    )
    if has_starred_named_expr or not assign_context:
        values = _infer_sequence_helper(self, context, infer_all_elements=not assign_context)
        if values == self.elts:
            # Do not create a new List if all elements are already inferred.
            yield self
            return
        
        new_seq = type(self).create_instance(
            lineno=self.lineno, col_offset=self.col_offset, elts=values,
        )
        yield fix_ast(new_seq, self.parent)
    else:
        yield self

_infer_List = _infer_sequence
_infer_Tuple = _infer_sequence
_infer_Set = _infer_sequence

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
      ast.FloorDiv: lambda a, b: a // b,
      ast.Mod    : lambda a, b: a % b,
      ast.Pow    : lambda a, b: a**b,
      ast.LShift : lambda a, b: a << b,
      ast.RShift : lambda a, b: a >> b,
      ast.BitOr  : lambda a, b: a | b,
      ast.BitAnd : lambda a, b: a & b,
      ast.BitXor : lambda a, b: a ^ b,
      ast.MatMult: lambda a, b: a @ b,
      
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

import operator as operatorlib
_AUGMENTED_OPERATORS = {
    ast.Add    : lambda a, b: operatorlib.iadd(a,b),
    ast.Sub    : lambda a, b: operatorlib.isub(a,b),
    ast.Mult   : lambda a, b: operatorlib.imul(a,b),
    ast.Div    : lambda a, b: operatorlib.itruediv(a,b),
    ast.FloorDiv: lambda a, b: operatorlib.ifloordiv(a,b),
    ast.Mod    : lambda a, b: operatorlib.imod(a,b),
    ast.Pow    : lambda a, b: operatorlib.ipow(a,b),
    ast.LShift : lambda a, b: operatorlib.ilshift(a,b),
    ast.RShift : lambda a, b: operatorlib.irshift(a,b),
    ast.BitOr  : lambda a, b: operatorlib.ior(a,b),
    ast.BitAnd : lambda a, b: operatorlib.iand(a,b),
    ast.BitXor : lambda a, b: operatorlib.ixor(a,b),
    ast.MatMult: lambda a, b: operatorlib.imatmul(a,b),
}

def _invoke_binop_inference(left: ASTNodeT, opnode: Union[_typing.BinOp, _typing.AugAssign], op:ast.operator, right: ASTNodeT, context: OptionalInferenceContext) -> InferResult:
    """
    Infer a binary operation between a left operand and a right operand.

    This is used by both normal binary operations and augmented binary
    operations.

    :note: left and right are inferred nodes.
    """
    # This implementation only support litreral types
    # see https://github.com/PyCQA/astroid/blob/58f470b993e368a82f545376c51a3beda83b5f74/astroid/inference.py#L715
    # for a more generic implementation.

    operators = _AUGMENTED_OPERATORS if isinstance(opnode, ast.AugAssign) else _OPPERATORS

    try:
        operator_meth = operators[type(op)]
    except KeyError:
        opnode._report(f"Unsupported operation: op={op}")
        yield nodes.Uninferable
        return
    try:
        literal_left = left.literal_eval()
        literal_right = right.literal_eval()
    except ValueError:
        # Unlike astroid, we can't infer binary operations on nodes that can't be evaluated as literals.
        opnode._report(f"Uninferable operation: lhs={left}, rhs={right}")
        yield nodes.Uninferable
        return
    try:
        inferred_literal = operator_meth(literal_left, literal_right)
    except Exception as e:
        # wrong types
        opnode._report(f"Operation failed ({e.__class__.__name__}): {e}; lhs={left}, rhs={right}")
        raise exceptions.InferenceError(node=opnode)

    yield fix_ast(literal_to_ast(inferred_literal), parent=opnode.parent)

@yes_if_nothing_inferred
@path_wrapper
def _infer_BinOp(self: _typing.BinOp, context: OptionalInferenceContext) -> InferResult:
    """
    Binary operation inference logic.

    :note: From astroid's inference._infer_binop() function.
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
            self._report(f"Uninferable binary operation: lhs={lhs}, rhs={rhs}")
            yield nodes.Uninferable
            return

        yield from _invoke_binop_inference(lhs, self, self.op, rhs, context)

def _infer_lhs(node: ast.expr, context:InferenceContext) -> InferResult:
    # won't work with a path wrapper
    """
    Infers the left hand side in augmented binary operations.

    @note: It only supports ast.Name instances at the moment.
    """
    if isinstance(node, ast.Name):
        yield from _infer_name(node, context)
    else:
        # TODO: we could support Attribute and Subscript nodes in the future
        node._report(f"Uninferable left hand side: {node.__class__.__name__!r} nodes are supported at the moment")
        yield nodes.Uninferable

@raise_if_nothing_inferred
@path_wrapper
def _infer_AugAssign(self:_typing.AugAssign, context: OptionalInferenceContext=None) -> InferResult:
    """Inference logic for augmented binary operations."""
    context = context or self._parser._new_context()
    lhs_context = copy_context(context)
    rhs_context = copy_context(context)
    lhs_iter = _infer_lhs(self.target, context=lhs_context)
    rhs_iter = infer(self.value, context=rhs_context) # type:ignore[attr-defined]

    for lhs, rhs in itertools.product(lhs_iter, rhs_iter):
        if any(value is nodes.Uninferable for value in (rhs, lhs)):
            # Don't know how to process this.
            self._report(f"Uninferable augmented assigment: lhs={lhs}, rhs={rhs}")
            yield nodes.Uninferable
            return

        yield from _invoke_binop_inference(lhs, self, self.op, rhs, rhs_context)
        
# Defers to self.value.infer()
def _infer_Expr(self:_typing.Expr, context: OptionalInferenceContext=None) -> InferResult:
    return self.value.infer(context=context) # type:ignore[attr-defined, no-any-return]

@raise_if_nothing_inferred
@path_wrapper
def _infer_alias(self:_typing.alias, context: OptionalInferenceContext=None) -> InferResult:
    modname = nodes.get_origin_module(self)
    try:
        ast_mod = self._parser.modules[modname]
    except KeyError:
        # we don't have this module in the system
        self._report(f"No module named {modname!r} in the system")
        yield nodes.Uninferable
        return

    if isinstance(self.parent, ast.ImportFrom):
        asname = self.name
        try:
            context = copy_context(context, self._parser._inference_cache)
            stmts = get_attr(ast_mod, asname, ignore_locals=ast_mod is self.root)
            yield from _infer_stmts(stmts, context)
        except exceptions.AttributeInferenceError as error:
            raise exceptions.InferenceError(
                str(error), target=self, attribute=asname, context=context
            ) from error
    else:
        yield ast_mod


# def _infer_Subscript(self:_typing.Subscript, context: OptionalInferenceContext=None) -> InferResult:
#     yield
#     return
#     # TODO
