"""
A fallback `ast.unparse` function that works with a minimal subset of nodes. 
"""

# This was originally the code providing the get_value() function in griffe/agents/nodes.py
# unparse() is a better name for this function since it's how it's called in the standard library.

from __future__ import annotations

import ast
import sys
from typing import Any, Callable, Type

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


_node_value_map: dict[Type[ast.AST], Callable[[Any], str]] = {
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


def _get_value(node: ast.AST) -> str:
    return _node_value_map[type(node)](node)

def get_value(node: ast.AST | None) -> str | None:
    """
    Same as `unparse` but accepts `None` values.
    """
    if node is None:
        return None
    return _node_value_map[type(node)](node)

def unparse(node:ast.AST) -> str:
    """Extract a complex value as a string.

    Parameters:
        node: The node to extract the value from.

    Returns:
        The unparsed code of the node.
    """
    return _node_value_map[type(node)](node)
