
import ast

import pytest

from astuce import nodes, inference
from . import AstuceTestCase, require_version

class Parse__all__Test(AstuceTestCase):

    def test_parse__all__(self):
        ...

    expressions = \
        [
            # operations
            "b + c",
            "b - c",
            "b * c",
            "b / c",
            "b // c",
            "b ** c",
            "b ^ c",
            "b & c",
            "b | c",
            "b @ c",
            "b % c",
            "b >> c",
            "b << c",
            # unary operations
            "+b",
            "-b",
            "~b",
            # comparisons
            "b == c",
            "b >= c",
            "b > c",
            "b <= c",
            "b < c",
            "b != c",
            # boolean logic
            "b and c",
            "b or c",
            "not b",
            # identify
            "b is c",
            "b is not c",
            # membership
            "b in c",
            "b not in c",
        ]
    
    def test_building_value_from_nodes(self):
        """Test building value from AST nodes."""
        for expression in self.expressions:
            module = self.parse(f"a = {expression}")
            assert "a" in module.locals
            value = module.locals["a"][0].statement.value
            unparsed = value.unparse().strip()

            # Workaround the extra parenthesis added by the unparse() function.
            if unparsed.startswith('(') and unparsed.endswith(')'):
                unparsed = unparsed[1:-1]

            assert unparsed == expression
            assert inference.get_value(value) == expression
            


# @pytest.mark.parametrize(
#     "statements",
#     [
#         """__all__ = moda_all + modb_all + modc_all + ["CONST_INIT"]""",
#         """__all__ = ["CONST_INIT", *moda_all, *modb_all, *modc_all]""",
#         """
#         __all__ = ["CONST_INIT"]
#         __all__ += moda_all + modb_all + modc_all
#         """,
#         """
#         __all__ = moda_all + modb_all + modc_all
#         __all__ += ["CONST_INIT"]
#         """,
#         """
#         __all__ = ["CONST_INIT"]
#         __all__ += moda_all
#         __all__ += modb_all + modc_all
#         """,
#     ],
# )
# def test_parse_complex__all__assignments(statements):
#     """Check our ability to expand exports based on `__all__` [augmented] assignments.
#     Parameters:
#         statements: Parametrized text containing `__all__` [augmented] assignments.
#     """
#     with temporary_pypackage("package", ["moda.py", "modb.py", "modc.py"]) as tmp_package:
#         tmp_package.path.joinpath("moda.py").write_text("CONST_A = 1\n\n__all__ = ['CONST_A']")
#         tmp_package.path.joinpath("modb.py").write_text("CONST_B = 1\n\n__all__ = ['CONST_B']")
#         tmp_package.path.joinpath("modc.py").write_text("CONST_C = 2\n\n__all__ = ['CONST_C']")
#         code = """
#             from package.moda import *
#             from package.moda import __all__ as moda_all
#             from package.modb import *
#             from package.modb import __all__ as modb_all
#             from package.modc import *
#             from package.modc import __all__ as modc_all
#             CONST_INIT = 0
#         """
#         tmp_package.path.joinpath("__init__.py").write_text(dedent(code) + dedent(statements))

#         loader = GriffeLoader(search_paths=[tmp_package.tmpdir])
#         package = loader.load_module(tmp_package.name)
#         loader.resolve_aliases()

#         assert package.exports == {"CONST_INIT", "CONST_A", "CONST_B", "CONST_C"}
