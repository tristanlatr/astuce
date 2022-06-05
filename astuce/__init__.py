"""
Some `ast.AST` inference helpers.
"""

import ast
import inspect

from .nodes import ASTNode, Instance
# from .expressions import Name, Expression
# from .inference import (parse__all__, get_annotation, get_value, 
#                         get_name, get_names, get_instance_names)

##### Dynamically path the ast.AST classes.

_patched = False

def _patch_ast() -> None:
    """Extend the base `ast.AST` class to provide more functionality."""
    global _patched  # noqa: WPS420
    if _patched:
        return
    
    # Patch
    for name, member in inspect.getmembers(ast):
        if name not in ["AST",
             "stmt", 
             "expr", 
             "operator", 
             "mod", 
             "expr_context",
             "boolop",
             "unaryop",
             "cmpop",
             "excepthandler",
             "type_ignore", # Ignore classes that are not concrete
             ] and inspect.isclass(member):
            if issubclass(member, ast.AST) and ASTNode not in member.mro():  # noqa: WPS609
                member.__bases__ = (*member.__bases__, ASTNode)  # noqa: WPS609
            if name in ["Constant", "List", "Tuple", "Set", "Dict"]:
                if issubclass(member, ast.AST) and Instance not in member.mro():  # noqa: WPS609
                    member.__bases__ = (*member.__bases__, Instance)  # noqa: WPS609
    _patched = True  # noqa: WPS122,WPS442

_patch_ast()
