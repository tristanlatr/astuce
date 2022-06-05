from __future__ import annotations

import ast

from astuce import nodes
from astuce._assigned_statements import assigned_stmts
from astuce.helpers import nodes_of_class
from . import fromtext, AstuceTestCase


def assertNameNodesEqual(nodes_list_expected: list[str], nodes_list_got: list[ast.Name]) -> None:
        assert len(nodes_list_expected)==len(nodes_list_got)
        for node in nodes_list_got:
            assert isinstance(node, ast.Name)
        for node, expected_name in zip(nodes_list_got, nodes_list_expected):
            assert expected_name == node.id

def assertConstNodesEqual(nodes_list_expected: list[object], nodes_list_got: list[nodes.ASTNode]) -> None:
        assert len(nodes_list_expected) == len(nodes_list_got)

        for node, expected_value in zip(nodes_list_got, nodes_list_expected):
            assert expected_value == node.literal_eval()


class TestAssignedStatements(AstuceTestCase):


# Not in the scope currently
# def test_assigned_stmts_simple_for(self) -> None:
#         mod = fromtext(
#             """
#         for a in (1, 2, 3):  #@
#           pass

#         for b in range(3): #@
#           pass
#         """
#         )
#         assign_stmts = mod.body

#         for1_assnode = next(assign_stmts[0].nodes_of_class(nodes.AssignName))
#         assigned = list(_assigned_statements.assigned_stmts(for1_assnode))
#         assertConstNodesEqual([1, 2, 3], assigned)

#         for2_assnode = next(assign_stmts[1].nodes_of_class(nodes.AssignName))
#         with pytest.raises(exceptions.InferenceError):
#             _assigned_statements.assigned_stmts(for2_assnode)

    def test_assigned_stmts_assignments(self) -> None:
        assign_stmts = fromtext(
            """
            c = a #@

            d, e = b, c #@
            """
            ).body

        simple_assnode = next(nodes_of_class(assign_stmts[0], ast.Name, predicate=nodes.is_assign_name))
        assigned = list(assigned_stmts(simple_assnode))
        assertNameNodesEqual(["a"], assigned)

        assnames = nodes_of_class(assign_stmts[1], ast.Name, predicate=nodes.is_assign_name)
        simple_mul_assnode_1 = next(assnames)
        assigned = list(assigned_stmts(simple_mul_assnode_1))
        assertNameNodesEqual(["b"], assigned)
        simple_mul_assnode_2 = next(assnames)
        assigned = list(assigned_stmts(simple_mul_assnode_2))
        assertNameNodesEqual(["c"], assigned)

    def test_assigned_stmts_annassignments(self) -> None:
        annassign_stmts = fromtext(
            """
            a: str = "abc"  #@
            b: str  #@
            """
            ).body

        simple_annassign_node = next(nodes_of_class(annassign_stmts[0], ast.Name, predicate=nodes.is_assign_name))
        assigned = list(assigned_stmts(simple_annassign_node))
        
        assert len(assigned) == 1
        assert isinstance(assigned[0], ast.Constant)
        assert assigned[0].value == "abc"

        empty_annassign_node = next(nodes_of_class(annassign_stmts[1], ast.Name, predicate=nodes.is_assign_name))
        assigned = list(assigned_stmts(empty_annassign_node))
        
        assert len(assigned) == 1
        assert assigned[0] is nodes.Uninferable

    def test_not_passing_uninferable_in_seq_inference(self) -> None:

        parsed = fromtext(
            """
            a = []
            x = [a*2, a]*2*2
            """
            )

        for node in nodes_of_class(parsed, ast.Name, predicate=nodes.is_assign_name):
            assert nodes.Uninferable not in list(node.infer())
