
# TODO list:

- [DONE] Finish code in _assigned_statements.py 
- [DONE] and plug it in with _infer_assign_name. 
- Improve the documentation of _infer_assign_name to link to the astroid name of this method.
- [PROPOSED] Clarify API that is going to be used to access class/module level variables.
- Invalidate the inference cache everytime a new module is parsed.
- Adjust _infer_Call to return an 'Instance' of the annotated type if the function uses type annotation.
- Adjust _infer_Call to return an inferred node if we're talking about builtins (and all parties are inferable)
- First apply set of transformations, as described in [Scalpel 2.1 Code Rewriter.](https://arxiv.org/pdf/2202.11840.pdf).
    - `ast.Str`, `ast.Bytes`, `ast.Num` to `ast.Constant` to ease support for python 3.6.
    - `__all__.extend(X)` -> `__all__ += X` (only at the module statements level)
    - `__all__.append(X)` -> `__all__ += [X]` (only at the module statements level)
    - `list()` -> `[]`, same for other builtins.


# Notes:
- `list.pop()` is a good example where mutation and return value are important, it could be hard to make work...

# How-to handle objet mutations?

## New idea:

- Do not infer list mutations, instead use code rewriter to transform list mutations in augmented assignments.
  For the case of `__all__` variable, this does not needs to be a iterative process.

## Older idea: 

- Store references to all ast.Name instances with a load context
- In what kind of data structure?
    - It should be working fairly like the locals dictionnary
    - So the key should be a string and the value list of ast.Name instances
    - When the ast.Name is part of an ast.Attribute, walk the tree until the top ast.Attribute and use the dottedname as the key
    
    This code:
        data = []
        data.append(a)
        data.extend(b)

    Would give:
        locals = {'data': [<ast.Name 'data'>]}
        loadnames = {
            'data.append': [<ast.Name 'append'>],
            'data.extend': [<ast.Name 'extend'>],
        }


    - To do the matching, search for data.* in the loadname dictionary.
    - infer_load_name.infer_name should be adjusted such that it looks up in this dictionnary and 
        applies the supported mutations to each inferable results, 
        - Use the same filter_stmt() code to filter the applicable loadnames statements

# Proposed API

```python

from astuce import Parser
# maybe it could take an options parameter to tweak some stuff.
parser = Parser() 

mod1 = parser.parse('''
from mod2 import l as _l
l = ['f', 'k']
l.extend(_l)
''')

mod2 = parser.parse('''
l = ('i', 'j')
''')

inferred = list(mod2.infer_name('l'))
assert len(inferred) == 1
assert inferred[0].literal_eval() == ['f', 'k', 'i', 'j']

```

