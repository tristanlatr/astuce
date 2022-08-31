
# TODO list:

- Adjust _infer_Call to return an 'Instance' of the annotated type if the function uses type annotation.
- Adjust _infer_Call to return an inferred node if we're talking about builtins (and all parties are inferable)
- First apply set of transformations, as described in [Scalpel 2.1 Code Rewriter.](https://arxiv.org/pdf/2202.11840.pdf)
    - `ast.Str`, `ast.Bytes`, `ast.Num` to `ast.Constant` to ease support for python 3.6.
    - `list()` -> `[]`, same for other builtins.
    - Rewrite simple attribute assigments outside out class scope inside the class, meaning::
        class C:
            ...
        def __init__C(self, x, y):
            ...
        C.__init__ = __init__C

      Into::
        class C:
            def __init__(self, x, y):
                ...
        __init__C = C.__init__

      TODO: check if this is actually correct.

- Investigate manners to move away from patching the AST classes, but without maintaining a set of node class.
- Document the core principles of astuce:
  - The inference system.
    - Name inference is recursive:
        - An `ast.Name` will be looked up and resolve to an `ast.Import` node, that will be inferred to a `ast.Module` node. 
    - Other kind of expression inference implies inference of the nodes directly part of the expression.
    - As a general rule, inference on statements (ast.stmt) either return self or Uninferable, an exception to that rules are augmented assigments.
  - Limitations: 
    - Will not proceed to inter-procedural analysis, this is not in the scope of this project.
    - The filter statement function does not provide path sensitive information. Nevertheless, utilities in this library can help building control flow graphs and together build a more precise inference system. Though, some simple constraints handling could be handled: https://github.com/PyCQA/astroid/pull/1189
    - Type hints will be considered as a source of information rather than a post-condition to check, this is not a type checker.
        - Calling infer() on a ast.Call node will most likely resulting into Uninferable, though some support migh be added for builtins.
- Implement unary operator inference
- Implement comparators inference
- Implement https://github.com/PyCQA/astroid/pull/1610/files

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
    - _infer_name() should be adjusted such that it looks up in this dictionnary and 
        applies the supported mutations to each inferable results, 
        - Use the same filter_stmt() code to filter the applicable loadnames statements
