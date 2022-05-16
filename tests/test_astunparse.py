
from astuce import _astunparse
from . import AstuceTestCase

class TestAstUnparseFunction(AstuceTestCase):

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
            unparsed = value.unparse()
            assert unparsed == expression
            assert _astunparse.unparse(value) == expression
