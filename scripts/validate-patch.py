"""
This script simply checks that the astuce/__init__.py 
file effectively patches all the AST classes. 

It's supposed to fail when a new node class is added, 
so we know we must add a new patch for it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import requests
from astuce.inference import safe_infer
from astuce.parser import parse
from astuce.nodes import nodes_of_class

# Ignore classes that are not concrete
exclude_list = ["AST",
                "stmt", 
                "expr", 
                "operator", 
                "mod", 
                "expr_context",
                "boolop",
                "unaryop",
                "cmpop",
                "excepthandler",
                "type_ignore", 
                "slice",
                "pattern",
                # Python2 classes
                "AugStore", 
                "AugLoad",
                "Param",
                ""]

def patched_names(astuce_init_ast:ast.Module) -> set[str]:
    # Get the names of the classes that we pat by looking at the 
    # addMixinPatch() calls.

    def predicate(call: ast.Call) -> bool:
        return call.func.unparse().endswith('addMixinPatch')

    s = set()
    
    for node in nodes_of_class(astuce_init_ast, ast.Call, predicate):
        assert isinstance(node, ast.Call)
        v = safe_infer(node.args[1])
        if not v:
            continue
        _name = ast.literal_eval(v)
        assert isinstance(_name, str)
        s.add(_name)
    
    return s

def ast_classes(ast_stubs_ast:ast.Module) -> set[str]:
    s = set()
    
    for node in nodes_of_class(ast_stubs_ast, ast.ClassDef):
        _name = node.name
        if _name in exclude_list:
            continue
        s.add(_name)
    
    return s

if __name__ == "__main__":

    ast_stubs_contents = requests.get('https://raw.githubusercontent.com/python/typeshed/master/stdlib/_ast.pyi').text
    astuce_init_contents = (Path(__file__).parent.parent / 'astuce' / '__init__.py').read_text()

    classes = ast_classes(parse(ast_stubs_contents, modname='_ast'))
    names = patched_names(parse(astuce_init_contents, modname='astuce', is_package=True))
    extras = set()
    missing = set()

    err = None
    if names!=classes:
        if names.issuperset(classes):
            extras = names.difference(classes)
            print(f"Patching unseless classes ({len(extras)}): {', '.join(extras)}")
            err = True
        
        elif classes.issuperset(names):
            missing = classes.difference(names)
            print(f"Missing classes ({len(missing)}): {', '.join(missing)}")
            err = True

    if err:
        if missing:
            print('Maybe fix it by adding the following statements?')
            for m in sorted(missing):
                print(f"_patcher.addMixinPatch(ast, {m!r}, [ASTNode])")
        exit(1)
    else:
        print("Patch should include all classes")
    