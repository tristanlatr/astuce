"""This module contains utilities for extracting information from nodes."""

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
        logger.debug(f"Cannot parse __all__ assignment: {get_value(node.value)} ({error})")
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
# values
def _get_add_value(node: ast.Add) -> str:
    return "+"


def _get_and_value(node: ast.And) -> str:
    return " and "


def _get_arguments_value(node: ast.arguments) -> str:
    return ", ".join(arg.arg for arg in node.args)


def _get_attribute_value(node: ast.Attribute) -> str:
    return f"{_get_value(node.value)}.{node.attr}"


def _get_binop_value(node: ast.BinOp) -> str:
    return f"{_get_value(node.left)} {_get_value(node.op)} {_get_value(node.right)}"


def _get_bitor_value(node: ast.BitOr) -> str:
    return "|"


def _get_bitand_value(node: ast.BitAnd) -> str:
    return "&"


def _get_bitxor_value(node: ast.BitXor) -> str:
    return "^"


def _get_boolop_value(node: ast.BoolOp) -> str:
    return _get_value(node.op).join(_get_value(value) for value in node.values)


def _get_call_value(node: ast.Call) -> str:
    posargs = ", ".join(_get_value(arg) for arg in node.args)
    kwargs = ", ".join(_get_value(kwarg) for kwarg in node.keywords)
    if posargs and kwargs:
        args = f"{posargs}, {kwargs}"
    elif posargs:
        args = posargs
    elif kwargs:
        args = kwargs
    else:
        args = ""
    return f"{_get_value(node.func)}({args})"


def _get_compare_value(node: ast.Compare) -> str:
    left = _get_value(node.left)
    ops = [_get_value(op) for op in node.ops]
    comparators = [_get_value(comparator) for comparator in node.comparators]
    return f"{left} " + " ".join(f"{op} {comp}" for op, comp in zip(ops, comparators))


def _get_comprehension_value(node: ast.comprehension) -> str:
    target = _get_value(node.target)
    iterable = _get_value(node.iter)
    conditions = [_get_value(condition) for condition in node.ifs]
    value = f"for {target} in {iterable}"
    if conditions:
        value = f"{value} if " + " if ".join(conditions)
    if node.is_async:
        value = f"async {value}"
    return value


def _get_constant_value(node: ast.Constant) -> str:
    return repr(node.value)


def _get_constant_value_no_repr(node: ast.Constant) -> str:
    return str(node.value)


def _get_dict_value(node: ast.Dict) -> str:
    pairs = zip(node.keys, node.values)
    gen = (f"{'None' if key is None else _get_value(key)}: {_get_value(value)}" for key, value in pairs)  # noqa: WPS509
    return "{" + ", ".join(gen) + "}"


def _get_dictcomp_value(node: ast.DictComp) -> str:
    key = _get_value(node.key)
    value = _get_value(node.value)
    generators = [_get_value(gen) for gen in node.generators]
    return f"{{{key}: {value} " + " ".join(generators) + "}"


def _get_div_value(node: ast.Div) -> str:
    return "/"


def _get_ellipsis_value(node: ast.Ellipsis) -> str:
    return "..."


def _get_eq_value(node: ast.Eq) -> str:
    return "=="


def _get_floordiv_value(node: ast.FloorDiv) -> str:
    return "//"


def _get_formatted_value(node: ast.FormattedValue) -> str:
    return f"{{{_get_value(node.value)}}}"


def _get_generatorexp_value(node: ast.GeneratorExp) -> str:
    element = _get_value(node.elt)
    generators = [_get_value(gen) for gen in node.generators]
    return f"{element} " + " ".join(generators)


def _get_gte_value(node: ast.NotEq) -> str:
    return ">="


def _get_gt_value(node: ast.NotEq) -> str:
    return ">"


def _get_ifexp_value(node: ast.IfExp) -> str:
    return f"{_get_value(node.body)} if {_get_value(node.test)} else {_get_value(node.orelse)}"


def _get_invert_value(node: ast.Invert) -> str:
    return "~"


def _get_in_value(node: ast.In) -> str:
    return "in"


def _get_is_value(node: ast.Is) -> str:
    return "is"


def _get_isnot_value(node: ast.IsNot) -> str:
    return "is not"


def _get_joinedstr_value(node: ast.JoinedStr) -> str:
    _node_value_map[ast.Constant] = _get_constant_value_no_repr
    result = repr("".join(_get_value(value) for value in node.values))
    _node_value_map[ast.Constant] = _get_constant_value
    return result


def _get_keyword_value(node: ast.keyword) -> str:
    return f"{node.arg}={_get_value(node.value)}"


def _get_lambda_value(node: ast.Lambda) -> str:
    return f"lambda {_get_value(node.args)}: {_get_value(node.body)}"


def _get_list_value(node: ast.List) -> str:
    return "[" + ", ".join(_get_value(el) for el in node.elts) + "]"


def _get_listcomp_value(node: ast.ListComp) -> str:
    element = _get_value(node.elt)
    generators = [_get_value(gen) for gen in node.generators]
    return f"[{element} " + " ".join(generators) + "]"


def _get_lshift_value(node: ast.LShift) -> str:
    return "<<"


def _get_lte_value(node: ast.NotEq) -> str:
    return "<="


def _get_lt_value(node: ast.NotEq) -> str:
    return "<"


def _get_matmult_value(node: ast.MatMult) -> str:
    return "@"


def _get_mod_value(node: ast.Mod) -> str:
    return "%"


def _get_mult_value(node: ast.Mult) -> str:
    return "*"


def _get_name_value(node: ast.Name) -> str:
    return node.id


def _get_not_value(node: ast.Not) -> str:
    return "not "


def _get_noteq_value(node: ast.NotEq) -> str:
    return "!="


def _get_notin_value(node: ast.NotIn) -> str:
    return "not in"


def _get_or_value(node: ast.Or) -> str:
    return " or "


def _get_pow_value(node: ast.Pow) -> str:
    return "**"


def _get_rshift_value(node: ast.RShift) -> str:
    return ">>"


def _get_set_value(node: ast.Set) -> str:
    return "{" + ", ".join(_get_value(el) for el in node.elts) + "}"


def _get_setcomp_value(node: ast.SetComp) -> str:
    element = _get_value(node.elt)
    generators = [_get_value(gen) for gen in node.generators]
    return f"{{{element} " + " ".join(generators) + "}"


def _get_slice_value(node: ast.Slice) -> str:
    value = f"{_get_value(node.lower) if node.lower else ''}:{_get_value(node.upper) if node.upper else ''}"
    if node.step:
        value = f"{value}:{_get_value(node.step)}"
    return value


def _get_starred_value(node: ast.Starred) -> str:
    return _get_value(node.value)


def _get_sub_value(node: ast.Sub) -> str:
    return "-"


def _get_subscript_value(node: ast.Subscript) -> str:
    subscript = _get_value(node.slice)
    if isinstance(subscript, str):
        subscript = subscript.strip("()")
    return f"{_get_value(node.value)}[{subscript}]"


def _get_tuple_value(node: ast.Tuple) -> str:
    return "(" + ", ".join(_get_value(el) for el in node.elts) + ")"


def _get_uadd_value(node: ast.UAdd) -> str:
    return "+"


def _get_unaryop_value(node: ast.UnaryOp) -> str:
    return f"{_get_value(node.op)}{_get_value(node.operand)}"


def _get_usub_value(node: ast.USub) -> str:
    return "-"


def _get_yield_value(node: ast.Yield) -> str:
    if node.value is None:
        return repr(None)
    return _get_value(node.value)


_node_value_map: dict[Type[AST], Callable[[Any], str]] = {
    # type(None): lambda _: repr(None),
    ast.Add: _get_add_value,
    ast.And: _get_and_value,
    ast.arguments: _get_arguments_value,
    ast.Attribute: _get_attribute_value,
    ast.BinOp: _get_binop_value,
    ast.BitAnd: _get_bitand_value,
    ast.BitOr: _get_bitor_value,
    ast.BitXor: _get_bitxor_value,
    ast.BoolOp: _get_boolop_value,
    ast.Call: _get_call_value,
    ast.Compare: _get_compare_value,
    ast.comprehension: _get_comprehension_value,
    ast.Constant: _get_constant_value,
    ast.DictComp: _get_dictcomp_value,
    ast.Dict: _get_dict_value,
    ast.Div: _get_div_value,
    ast.Ellipsis: _get_ellipsis_value,
    ast.Eq: _get_eq_value,
    ast.FloorDiv: _get_floordiv_value,
    ast.FormattedValue: _get_formatted_value,
    ast.GeneratorExp: _get_generatorexp_value,
    ast.GtE: _get_gte_value,
    ast.Gt: _get_gt_value,
    ast.IfExp: _get_ifexp_value,
    ast.In: _get_in_value,
    ast.Invert: _get_invert_value,
    ast.Is: _get_is_value,
    ast.IsNot: _get_isnot_value,
    ast.JoinedStr: _get_joinedstr_value,
    ast.keyword: _get_keyword_value,
    ast.Lambda: _get_lambda_value,
    ast.ListComp: _get_listcomp_value,
    ast.List: _get_list_value,
    ast.LShift: _get_lshift_value,
    ast.LtE: _get_lte_value,
    ast.Lt: _get_lt_value,
    ast.MatMult: _get_matmult_value,
    ast.Mod: _get_mod_value,
    ast.Mult: _get_mult_value,
    ast.Name: _get_name_value,
    ast.NotEq: _get_noteq_value,
    ast.Not: _get_not_value,
    ast.NotIn: _get_notin_value,
    ast.Or: _get_or_value,
    ast.Pow: _get_pow_value,
    ast.RShift: _get_rshift_value,
    ast.SetComp: _get_setcomp_value,
    ast.Set: _get_set_value,
    ast.Slice: _get_slice_value,
    ast.Starred: _get_starred_value,
    ast.Sub: _get_sub_value,
    ast.Subscript: _get_subscript_value,
    ast.Tuple: _get_tuple_value,
    ast.UAdd: _get_uadd_value,
    ast.UnaryOp: _get_unaryop_value,
    ast.USub: _get_usub_value,
    ast.Yield: _get_yield_value,
}

# TODO: remove once Python 3.8 support is dropped
if sys.version_info < (3, 9):

    def _get_index_value(node: ast.Index) -> str:
        return _get_value(node.value)

    _node_value_map[ast.Index] = _get_index_value


# TODO: remove once Python 3.7 support is dropped
if sys.version_info < (3, 8):

    def _get_bytes_value(node: ast.Bytes) -> str:
        return repr(node.s)

    def _get_nameconstant_value(node: ast.NameConstant) -> str:
        return repr(node.value)

    def _get_num_value(node: ast.Num) -> str:
        return repr(node.n)

    def _get_str_value(node: ast.Str) -> str:
        return repr(node.s)

    _node_value_map[ast.Bytes] = _get_bytes_value
    _node_value_map[ast.NameConstant] = _get_nameconstant_value
    _node_value_map[ast.Num] = _get_num_value
    _node_value_map[ast.Str] = _get_str_value


def _get_value(node: AST) -> str:
    return _node_value_map[type(node)](node)


def get_value(node: AST | None) -> str | None:
    """Extract a complex value as a string.

    Parameters:
        node: The node to extract the value from.

    Returns:
        The unparsed code of the node.
    """
    if node is None:
        return None
    return _node_value_map[type(node)](node)


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
