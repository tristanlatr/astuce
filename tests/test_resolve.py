# from sphinx-autoapi, we do not currently use the resolve_qualname function, but tests are there anyway.


import ast
from textwrap import dedent
from typing import Iterator, Tuple
import pytest

from astuce import parser, nodes
from . import AstuceTestCase, fromtext

@pytest.mark.parametrize(
        ("source", "expected"), 
        [("var: typing.Generic[T]", "typing.Generic -> typing.Generic"), 
        ("var: typing.Generic[T, _KV]", "typing.Generic -> typing.Generic"),
        ("from typing import Generic\nvar: Generic[T]", "Generic -> typing.Generic"),
        ("from pydocspec import _model as m\nvar: m.TreeRoot[T]", "m.TreeRoot -> pydocspec._model.TreeRoot"),
        ("var: dict[str, str]", "dict -> dict"),]
    )
def test_node2fullname_nodes(source:str, expected:str) -> None:

    mod = fromtext(source)
    var = mod.locals['var'][0]
    assert isinstance(var, ast.Name)
    annassing = var.parent
    assert isinstance(annassing, ast.AnnAssign)
    ann = annassing.annotation
    dottedname = '.'.join(nodes.node2dottedname(ann))

    assert f"{dottedname} -> {ann.resolve(dottedname)}" == expected

class ResolveTest(AstuceTestCase):

    def test_resolve_function_argument(self,):
        mod = self.parse('''
        from typing import Any
        def func(a,b:int,c=True,*d,**e:Any):
            ...
        ''')
        func = mod.body[-1]
        assert isinstance(func, ast.FunctionDef)
        elips = func.body[0]
        assert func == mod.locals['func'][0]

        # Assert that we filter the right assigments when trying to lookup
        # a name that is not accessible in the context of the scope
        with pytest.raises(LookupError):
            True_node = func.args.defaults[0]
            assert True_node.lookup('a')

        assert func.lookup('a')[1] == [func.args.args[0]]

        assert func.resolve('a') == elips.resolve('a') == f"{func.qname}.a"
        assert func.resolve('b') == elips.resolve('b') == f"{func.qname}.b"
        assert func.resolve('c') == elips.resolve('c') == f"{func.qname}.c"
        assert func.resolve('d') == elips.resolve('d') == f"{func.qname}.d"
        assert func.resolve('e') == elips.resolve('e') == f"{func.qname}.e"
    
    def test_resolve_alias(self,):
        mod = self.parse('''
        from typing import Any
        AnyT = Any

        def func(a,b:int,c=True,*d,**e:Any):
            ...
        
        class klass:
            f = func
        ''')
        klass = mod.body[-1]
        assert isinstance(klass, ast.ClassDef)
        func = mod.body[-2]
        assert isinstance(klass, ast.ClassDef)

        assert func.resolve('AnyT') == klass.resolve('AnyT') == "typing.Any"
        assert klass.resolve('f') == func.qname == 'test.func'
       

def generate_module_names() -> Iterator[str]:
    for i in range(1, 5):
        yield ".".join("module{}".format(j) for j in range(i))

    yield "package.repeat.repeat"


def imported_basename_cases() -> Iterator[Tuple[str, str, str]]:
    for module_name in generate_module_names():
        import_ = "import {}".format(module_name)
        basename = "{}.ImportedClass".format(module_name)
        expected = basename

        yield (import_, basename, expected)

        import_ = "import {} as aliased".format(module_name)
        basename = "aliased.ImportedClass"

        yield (import_, basename, expected)

        if "." in module_name:
            from_name, attribute = module_name.rsplit(".", 1)
            import_ = "from {} import {}".format(from_name, attribute)
            basename = "{}.ImportedClass".format(attribute)
            yield (import_, basename, expected)

            import_ += " as aliased"
            basename = "aliased.ImportedClass"
            yield (import_, basename, expected)

        import_ = "from {} import ImportedClass".format(module_name)
        basename = "ImportedClass"
        yield (import_, basename, expected)

        import_ = "from {} import ImportedClass as AliasedClass".format(module_name)
        basename = "AliasedClass"
        yield (import_, basename, expected)


def generate_args() -> Iterator[str]:
    for i in range(5):
        yield ", ".join("arg{}".format(j) for j in range(i))


def imported_call_cases() -> Iterator[Tuple[str, str, str]]:
    for args in generate_args():
        for import_, basename, expected in imported_basename_cases():
            basename += "({})".format(args)
            expected += "()"
            yield import_, basename, expected


@pytest.mark.parametrize(
    ("import_", "basename", "expected"), list(imported_basename_cases())
)
def test_can_get_full_imported_basename(import_:str, basename:str, expected:str) -> None:
    source = """
    {}
    class ThisClass({}):
        pass
    """.format(
        import_, basename
    )
    mod = fromtext(source)

    node = mod.body[-1]
    # This fails with keyerror? wtf
    # assert node == mod.locals['ThisClass'][0] 
    # assert node == mod.lookup('ThisClass')[1][0]

    assert isinstance(node, ast.ClassDef)
    basenames = node.resolve(node.bases[0].unparse())
    assert basenames == expected

@pytest.mark.parametrize(
    ("import_", "basename", "expected"), list(imported_call_cases())
)
def test_can_get_full_function_basename(import_:str, basename:str, expected:str) -> None:
    source = """
    {}
    class ThisClass({}):
        pass
    """.format(
        import_, basename
    )
    mod = fromtext(source)

    node = mod.body[-1]
    # assert node == mod.locals['ThisClass'][0]
    assert isinstance(node, ast.ClassDef)
    basenames = node.resolve(node.bases[0].unparse())
    assert basenames == expected
