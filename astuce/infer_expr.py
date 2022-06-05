"""This module contains utilities for extracting information from nodes."""

# Definition of 'Looking-up':
# Looking up is the action of determining where a given name is beeing referenced, exluding ignorable statements.
# Lookups happends at the module scope, it does not return nodes outside of the current ast.Module and does not use the inference logic.

# Definition of 'Inference':
# Inference is the action to statically evaluate an AST node into another object (in our case also represented by AST node ) that express the runtime 
# behaviour. It uses the lookup logic. It should not use the Resolving logic.

# Definition of 'Resolving':
# Resolving a name is the action of looking it up in the current scope and expand this name to it's full dotted name.
# Name resolving is is charge to follow aliases, look for the definition node of an imported name in the parsed modules, etc. 
# The name resolving logic uses the inference logic, namely for aliases. 


from __future__ import annotations

import logging
import sys

import ast
from ast import AST

from functools import partial
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)

from .expressions import Name, Expression
from .nodes import ASTNode

def _join(sequence: list[str | Name| Expression], item:str) -> list[str | Name| Expression]:
    if not sequence:
        return []
    new_sequence = [sequence[0]]
    for element in sequence[1:]:
        new_sequence.extend((item, element))
    return new_sequence


def _parse__all__constant(node: ast.Constant) -> list[str]:
    try:
        return [node.value]
    except AttributeError:
        return [node.s]  # TODO: remove once Python 3.7 is dropped


def _parse__all__name(node: ast.Name) -> list[Name]:
    assert isinstance(node, ASTNode)
    return [Name(node.id, partial(node.scope.resolve, node.id))]


def _parse__all__starred(node: ast.Starred) -> list[str | Name]:
    return _parse__all__(node.value)


def _parse__all__sequence(node: ast.List | ast.Set | ast.Tuple,) -> list[str | Name]:
    sequence = []
    for elt in node.elts:
        sequence.extend(_parse__all__(elt))
    return sequence


def _parse__all__binop(node: ast.BinOp) -> list[str | Name]:
    left = _parse__all__(node.left)
    right = _parse__all__(node.right)
    return left + right


_node__all__map: dict[Type[Any], Callable[[Any], list[str | Name]]] = {  # noqa: WPS234
    ast.Constant: _parse__all__constant,  # type: ignore[dict-item]
    ast.Name: _parse__all__name,  # type: ignore[dict-item]
    ast.Starred: _parse__all__starred,
    ast.List: _parse__all__sequence,
    ast.Set: _parse__all__sequence,
    ast.Tuple: _parse__all__sequence,
    ast.BinOp: _parse__all__binop,
}

# TODO: remove once Python 3.7 support is dropped
if sys.version_info < (3, 8):

    def _parse__all__nameconstant(node: ast.NameConstant) -> list[Name]:
        return [node.value]

    def _parse__all__str(node: ast.Str) -> list[str]:
        return [node.s]

    _node__all__map[ast.NameConstant] = _parse__all__nameconstant
    _node__all__map[ast.Str] = _parse__all__str 


def _parse__all__(node: AST) -> list[str | Name]:
    return _node__all__map[type(node)](node)


def parse__all__(node: ast.Assign | ast.AugAssign) -> list[str | Name]:  # noqa: WPS120,WPS440
    """Get the values declared in `__all__`.

    Parameters:
        node: The assignment node.

    Returns:
        A set of names.
    """
    try:
        return _parse__all__(node.value)
    except KeyError as error:
        logger.debug(f"Cannot parse __all__ assignment: {node.value.unparse()} ({error})")
        return []


# ==========================================================
# annotations
def _get_attribute_annotation(node: ast.Attribute) -> Expression:
    left = _get_annotation(node.value)

    def resolver()->str: 
        assert isinstance(left, Name) 
        # TODO: check if this is the best way to handle the corner case when left is not a Name.
        return f"{left.full}.{node.attr}"

    right = Name(node.attr, resolver)
    return Expression(left, ".", right)


def _get_binop_annotation(node: ast.BinOp) -> Expression:
    left = _get_annotation(node.left)
    right = _get_annotation(node.right)
    return Expression(left, _get_annotation(node.op), right)


def _get_bitand_annotation(node: ast.BitAnd) -> str:
    return " & "


def _get_bitor_annotation(node: ast.BitOr) -> str:
    return " | "


def _get_call_annotation(node: ast.Call) -> Expression:
    posargs = Expression(*_join([_get_annotation(arg) for arg in node.args], ", "))
    kwargs = Expression(*_join([_get_annotation(kwarg) for kwarg in node.keywords], ", "))
    args: Expression | str
    if posargs and kwargs:
        args = Expression(posargs, ", ", kwargs)
    elif posargs:
        args = posargs
    elif kwargs:
        args = kwargs
    else:
        args = ""
    return Expression(_get_annotation(node.func), "(", args, ")")


def _get_constant_annotation(node: ast.Constant) -> str:
    return {type(...): lambda _: "..."}.get(type(node.value), repr)(node.value)


def _get_ellipsis_annotation(node: ast.Ellipsis) -> str:
    return "..."


def _get_ifexp_annotation(node: ast.IfExp) -> Expression:
    return Expression(
        _get_annotation(node.body),
        " if ",
        _get_annotation(node.test),
        " else",
        _get_annotation(node.orelse),
    )


def _get_invert_annotation(node: ast.Invert) -> str:
    return "~"


def _get_keyword_annotation(node: ast.keyword) -> Expression:
    return Expression(f"{node.arg}=", _get_annotation(node.value))


def _get_list_annotation(node: ast.List) -> Expression:
    return Expression("[", *_join([_get_annotation(el) for el in node.elts], ", "), "]")


def _get_name_annotation(node: ast.Name) -> Name:
    assert isinstance(node, ASTNode)
    return Name(node.id, partial(node.scope.resolve, node.id))


def _get_subscript_annotation(node: ast.Subscript) -> Expression:
    left = _get_annotation(node.value)
    subscript = _get_annotation(node.slice)
    return Expression(left, "[", subscript, "]")


def _get_tuple_annotation(node: ast.Tuple) -> Expression:
    return Expression(*_join([_get_annotation(el) for el in node.elts], ", "))


def _get_unaryop_annotation(node: ast.UnaryOp) -> Expression:
    return Expression(_get_annotation(node.op), _get_annotation(node.operand))


_node_annotation_map: dict[Type[AST], Callable[[Any], str | Name | Expression]] = {
    ast.Attribute: _get_attribute_annotation,
    ast.BinOp: _get_binop_annotation,
    ast.BitAnd: _get_bitand_annotation,
    ast.BitOr: _get_bitor_annotation,
    ast.Call: _get_call_annotation,
    ast.Constant: _get_constant_annotation,
    ast.Ellipsis: _get_ellipsis_annotation,
    ast.IfExp: _get_ifexp_annotation,
    ast.Invert: _get_invert_annotation,
    ast.keyword: _get_keyword_annotation,
    ast.List: _get_list_annotation,
    ast.Name: _get_name_annotation,
    ast.Subscript: _get_subscript_annotation,
    ast.Tuple: _get_tuple_annotation,
    ast.UnaryOp: _get_unaryop_annotation,
}

# TODO: remove once Python 3.8 support is dropped
if sys.version_info < (3, 9):

    def _get_index_annotation(node: ast.Index) -> str | Name | Expression:
        return _get_annotation(node.value)

    _node_annotation_map[ast.Index] = _get_index_annotation

# TODO: remove once Python 3.7 support is dropped
if sys.version_info < (3, 8):

    def _get_bytes_annotation(node: ast.Bytes) -> str:
        return repr(node.s)

    def _get_nameconstant_annotation(node: ast.NameConstant) -> str:
        return repr(node.value)

    def _get_num_annotation(node: ast.Num) -> str:
        return repr(node.n)

    def _get_str_annotation(node: ast.Str) -> str:
        return node.s

    _node_annotation_map[ast.Bytes] = _get_bytes_annotation
    _node_annotation_map[ast.NameConstant] = _get_nameconstant_annotation
    _node_annotation_map[ast.Num] = _get_num_annotation
    _node_annotation_map[ast.Str] = _get_str_annotation


def _get_annotation(node: AST) -> str | Name | Expression:
    return _node_annotation_map[type(node)](node)


def get_annotation(node: AST | None) -> str | Name | Expression | None:
    """Extract a resolvable annotation.

    Parameters:
        node: The annotation node.
        parent: The parent used to resolve the name.

    Returns:
        A string or resovable name or expression.
    """
    if node is None:
        return None
    return _get_annotation(node)


# ==========================================================
# names
def _get_attribute_name(node: ast.Attribute) -> str:
    return f"{get_name(node.value)}.{node.attr}"


def _get_name_name(node: ast.Name) -> str:
    return node.id


_node_name_map: dict[Type[AST], Callable[[Any], str]] = {
    ast.Name: _get_name_name,
    ast.Attribute: _get_attribute_name,
}


def get_name(node: AST) -> str:
    """Extract name from an assignment node.

    Parameters:
        node: The node to extract names from.

    Returns:
        A list of names.
    """
    return _node_name_map[type(node)](node)


def _get_assign_names(node: ast.Assign) -> list[str]:
    names = (get_name(target) for target in node.targets)
    return [name for name in names if name]


def _get_annassign_names(node: ast.AnnAssign) -> list[str]:
    name = get_name(node.target)
    return [name] if name else []


_node_names_map: dict[Type[AST], Callable[[Any], list[str]]] = {  # noqa: WPS234
    ast.Assign: _get_assign_names,
    ast.AnnAssign: _get_annassign_names,
}


def get_names(node: AST) -> list[str]:
    """Extract names from an assignment node.

    Parameters:
        node: The node to extract names from.

    Returns:
        A list of names.
    """
    return _node_names_map[type(node)](node)


def get_instance_names(node: AST) -> list[str]:
    """Extract names from an assignment node, only for instance attributes.

    Parameters:
        node: The node to extract names from.

    Returns:
        A list of names.
    """
    return [name.split(".", 1)[1] for name in get_names(node) if name.startswith("self.")]
