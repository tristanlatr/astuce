import ast
from typing import Any, Union
from ._typing import ASTNode as ASTNodeT

def qname_to_ast(name:str) -> Union[ast.Name, ast.Attribute]:
    parts = name.split('.')
    assert parts, "must not be empty"
    
    if len(parts)==1:
        return ast.Name(parts[0], ast.Load())
    else:
        return ast.Attribute(qname_to_ast('.'.join(parts[:-1])), parts[-1], ast.Load())

# Move this to inference.py or add a note saying it relies on 
# some nodes to be patched.
def literal_to_ast(ob:Any) -> ast.expr:
    """
    Transform a literal object into it's AST counterpart.
    
    The object provided may only consist of the following
    Python builtin types: strings, bytes, numbers, tuples, lists, dicts,
    sets, booleans, and None.

    Normally, ``AST`` and ``literal_to_ast(ast.literal_eval(AST))`` are equivalent.
    """
    def _convert(thing:Any) -> ast.expr:
        if isinstance(thing, tuple):
            return ast.Tuple.create_instance(elts=list(map(_convert, thing))) # type:ignore[no-any-return, attr-defined]
        elif isinstance(thing, list):
            return ast.List.create_instance(elts=list(map(_convert, thing))) # type:ignore[no-any-return, attr-defined]
        elif isinstance(thing, set):
            return ast.Set.create_instance(elts=list(map(_convert, thing))) # type:ignore[no-any-return, attr-defined]
        elif isinstance(thing, dict):
            values = []
            keys = []
            for k,v in thing.items():
                values.append(_convert(v))
                keys.append(_convert(k))
            return ast.Dict.create_instance(keys=keys, values=values) # type:ignore[no-any-return, attr-defined]
        elif isinstance(thing, (int, float, complex, bytes, str, bool)):
            return ast.Constant.create_instance(thing) # type:ignore[no-any-return, attr-defined]
        elif thing is None:
            return ast.Constant.create_instance(None) # type:ignore[no-any-return, attr-defined]
        raise ValueError(f"Not a literal: {thing!r}")
    return _convert(ob)

def fix_missing_parents(node:ASTNodeT, parent:ASTNodeT) -> ASTNodeT:
    """
    Fix the missing ``parent`` attribute, starting at node.
    Also setup the ``_parser`` attribute.
    """
    def _fix(_node:ASTNodeT, _parent:ASTNodeT) -> None:
        _parent._parser._init_new_node(_node, _parent)
        for child in _node.children:
            _fix(child, _node)
    _fix(node, parent)
    return node

def fix_ast(node:ASTNodeT, parent:ASTNodeT) -> ASTNodeT:
    """
    Fix a newly created AST tree to be compatible with astuce.
    """
    # TODO: Locations doesn't really makes sens for inferred nodes. 
    # But it's handy to have the context linenumber here.
    return fix_missing_parents(
        ast.fix_missing_locations(
            ast.copy_location(node, parent)), parent)
