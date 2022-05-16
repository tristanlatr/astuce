# from sphinx-autoapi, we do not currently use the resolve_qualname function, but tests are there anyway.


import ast
from textwrap import dedent
from typing import Iterator, Tuple
import pytest

from astuce import parser

_parse_mod = lambda text:parser.Parser().parse(dedent(text), modname='test')

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
    mod = _parse_mod(source)

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
    mod = _parse_mod(source)

    node = mod.body[-1]
    # assert node == mod.locals['ThisClass'][0]
    assert isinstance(node, ast.ClassDef)
    basenames = node.resolve(node.bases[0].unparse())
    assert basenames == expected
