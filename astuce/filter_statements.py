from __future__ import annotations

import ast
from typing import List, Optional, Tuple, Union
from .nodes import ASTNode, is_assign_name, is_del_name, are_exclusive, is_orelse, get_if_statement_ancestor
# TODO: we don't actaully need to import ASTNode here and is_assign_name, is_del_name should go into new module
# This avoid to have import this module from within the function in _lookup.py.

from ._typing import ASTstmt, LocalsAssignT, Module as ASTModuleT
"""
This module contains the code adjusted from astroid to filter statements. 
"""

# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
filter_stmts and helper functions. This function gets used in LocalsDictnodes.ASTNode._scope_lookup.
It is not considered public.
"""

OPTIONAL_ASSIGN_NODES = (ast.NamedExpr, ast.comprehension, ast.For, ast.AsyncFor)

# From astroid's FilterStmtsMixin
FILTER_STATEMENTS_NODES = (ast.ImportFrom, ast.Import, ast.ClassDef, ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)

# (
#     ast.AnnAssign, ast.Assert, 
#     ast.Assign, ast.AugAssign, 
#     ast.Break, ast.Continue, 
#     ast.Delete, ast.ExceptHandler, 
#     ast.Expr, ast.For, ast.Global, 
#     ast.If, ast.Import, ast.ImportFrom, 
#     ast.Nonlocal, ast.Pass, ast.Raise, 
#     ast.Return, ast.ClassDef, ast.FunctionDef, 
#     ast.Try, ast.While, ast.With)

# nodes that directly assigns/delete a value to a name
ASSIGNMENT_NODES = ( ast.arguments, ast.Delete,
                    ast.AnnAssign, ast.Assign, ast.AugAssign, 
                    ast.Import, ast.ImportFrom, ast.ExceptHandler, 
                    ast.For, ast.With, ast.NamedExpr, )
                    # MatchMapping, MatchStar MatchAs

# nodes that do not directly assigns a value to a name, but parent is maybe.
# the following expression can appear in assignment context:
PARENT_ASSIGNMENT_NODES = (ast.Name, ast.Attribute, ast.arg, ast.List, 
                           ast.Tuple, ast.Set, ast.Starred, ast.alias)

# isinstance(self, ast.AssignAttr, ast.AssignName, ast.DelAttr, ast.DelName, ast.node_classes.BaseContainer, ast.Starred
        # , ast.AnnAssign, ast.Arguments, ast.Assign, ast.AugAssign, ast.Delete, ast.ExceptHandler, ast.For, ast.MatchAs, 
        # ast.MatchMapping, ast.MatchStar, ast.NamedExpr, ast.Unknown, ast.With):

CONTAINER_NODES = (ast.List, ast.Set, ast.Tuple)

def get_assign_type(node: 'LocalsAssignT') -> 'ASTNode':
    """
    Get the node that assigned the name represented by the node. 

    For a `ast.Name`, return the parent `ast.Assign` or `ast.AnnAssign` node that define the name.

    For others, it return the statement it self.
    """

    def _should_use_parent_assign_type(node: 'ASTNode') -> bool:
        # mimics astroid.mixins.ParentAssignTypeMixin
        if isinstance(node, PARENT_ASSIGNMENT_NODES):
            if isinstance(node, (ast.Name, ast.Attribute)):
                return is_assign_name(node) or is_del_name(node)
            else:
                return True
        return False

    if _should_use_parent_assign_type(node):
        return get_assign_type(node.parent)
    return node

def optionally_assigns(self: 'ASTNode') -> bool:
    """
    Whether this node optionally assigns a variable.

    This is for loop assignments because loop won't necessarily perform an
    assignment if the loop has no iterations.
    """
    return isinstance(self, OPTIONAL_ASSIGN_NODES)

# TODO: Create a function to find the first common parent in beetween two nodes.
# Use it in are_exclusive() and also use in the same fashion to filter nodes based
# on pre-evaluated ifs conditions.

def _get_filtered_node_statements(
    base_node: 'ASTNode', stmt_nodes: List[LocalsAssignT]
) -> List[Tuple[LocalsAssignT, Union[ASTstmt, ASTModuleT]]]:
    """
    Returns the list of tuples (node, node.statement) for all stmt_nodes.
    
    Special handling for ExceptHandlers, see code comments.
    """
    statements = [(node, node.statement) for node in stmt_nodes]
    # Next we check if we have ExceptHandlers that are parent
    # of the underlying variable, in which case the last one survives
    if len(statements) > 1 and all(
        isinstance(stmt, ast.ExceptHandler) for _, stmt in statements
    ):
        statements = [
            (node, stmt) for node, stmt in statements if stmt.parent_of(base_node)
        ]
    return statements

def _get_filtered_stmts(self: 'ASTNode', base_node: 'ASTNode', node: 'LocalsAssignT', _stmts:List['ASTNode'], mystmt:Optional['ASTNode'] ) -> Tuple[List['ASTNode'], bool]:
    """
    :param self: the assign_type.
    :param base_node: the lookup context node in which the filtering happends.
    :param node: the LocalsAssignT node where the node to filter was assigned.
    :param _stmts: the already filtered statements (empty list on the first iteration)
    :param mystmt: the statement of the base node.
    """
    # self is assign_type
    if isinstance(self, FILTER_STATEMENTS_NODES):
        return _filter_statement_get_filtered_stmts(self, base_node, node, _stmts, mystmt)
    elif isinstance(self, ast.comprehension): # is this required?
        return _comprehension_get_filtered_stmts(self, base_node, node, _stmts, mystmt)
    elif isinstance(self, ASSIGNMENT_NODES) or isinstance(self, PARENT_ASSIGNMENT_NODES):
        return _assign_type_get_filtered_stmts(self, base_node, node, _stmts, mystmt)
    assert False, f"statement not supported: {self.__class__.__name__}"

def _filter_statement_get_filtered_stmts(self: 'ASTNode', _:'ASTNode', node: 'LocalsAssignT', _stmts:List['ASTNode'], mystmt:Optional['ASTNode']) -> Tuple[List['ASTNode'], bool]:
    # from astroid FilterStmtsMixin
    """method used in _filter_stmts to get statements and trigger break"""
    if self.statement is mystmt:
        # original node's statement is the assignment, only keep
        # current node (gen exp, list comp)
        return [node], True
    return _stmts, False

def _assign_type_get_filtered_stmts(
    self: 'ASTNode', lookup_node:'ASTNode', node: 'LocalsAssignT', _stmts:List['ASTNode'], mystmt:Optional['ASTNode']
) -> Tuple[List['ASTNode'], bool]:
    # from AssignTypeMixin
    """method used in filter_stmts"""
    if self is mystmt:
        return _stmts, True
    if self.statement is mystmt:
        # original node's statement is the assignment, only keep
        # current node (gen exp, list comp)
        return [node], True
    return _stmts, False

def _comprehension_get_filtered_stmts(self: 'ASTNode', lookup_node:'ASTNode', node: 'LocalsAssignT', stmts:List['ASTNode'], mystmt:Optional['ASTNode']) -> Tuple[List['ASTNode'], bool]:
    # from Comprehension
    """method used in filter_stmts"""
    if self is mystmt:
        if isinstance(lookup_node, (ast.Constant, ast.Name)): # type:ignore[unreachable]
            return [lookup_node], True

    elif self.statement is mystmt:
        # original node's statement is the assignment, only keeps
        # current node (gen exp, list comp)

        return [node], True

    return stmts, False

def filter_stmts(base_node: 'ASTNode', stmts:List[LocalsAssignT], frame: 'ASTNode', offset:int) -> List['ASTNode']:
    """
    Filter the given list of statements to remove ignorable statements.
    If base_node is not a frame itself and the name is found in the inner
    frame locals, statements will be filtered to remove ignorable
    statements according to base_node's location.

    :param stmts: The statements to filter. 
        This list generally comes from the ASTNode.locals atribute that 
        maps strings to `ast.Name` or `ast.Attribute`
    :type stmts: list(ASTNode)

    :param frame: The frame that all of the given statements belong to.
    :type frame: ASTNode
    :param offset: The line offset to filter statements up to.
    :type offset: int
    :returns: The filtered statements.
    :rtype: list(ASTNode)
    """
    # if offset == -1, my actual frame is not the inner frame but its parent
    #
    # class A(B): pass
    #
    # we need this to resolve B correctly
    if offset == -1:
        myframe = base_node.frame.parent.frame
    else:
        myframe = base_node.frame
        # If the frame of this node is the same as the statement
        # of this node, then the node is part of a class or
        # a function definition and the frame of this node should be the
        # the upper frame, not the frame of the definition.
        # For more information why this is important,
        # see Pylint issue #295.
        # For example, for 'b', the statement is the same
        # as the frame / scope:
        #
        # def test(b=1):
        #     ...
        if (
            base_node.parent
            and base_node.statement is myframe
            and myframe.parent
        ):
            myframe = myframe.parent.frame

    # mystmt is the statement of the base_node
    mystmt:Optional['ASTNode'] = None
    if base_node.parent:
        mystmt = base_node.statement

    # line filtering if we are in the same frame
    #
    # take care node may be missing lineno information (lineno=-1)
    if myframe is frame and mystmt and mystmt.lineno!=-1:
        assert mystmt.lineno is not None, mystmt
        mylineno = mystmt.lineno + offset
    else:
        # disabling lineno filtering
        mylineno = 0

    _stmts:List['ASTNode'] = [] # this variable is the return value of the function, it's the "filtered statements"
    _stmt_parents = []
    statements = _get_filtered_node_statements(base_node, stmts)
    
    # Iterate over all statements anf filter ignorables
    for node, stmt in statements:
        # Context: 
        # node: Statement name node
        # stmt: Statement node

        # line filtering is on and we have reached our location, break
        if stmt.lineno and stmt.lineno > mylineno > 0:
            break
        # Ignore decorators with the same name as the
        # decorated function
        # Fixes issue #375
        if mystmt is stmt and base_node._is_from_decorator:
            continue
        if node.has_base(base_node):
            break

        # if isinstance(node, EmptyNode):
        #     # EmptyNode does not have assign_type(), so just add it and move on
        #     _stmts.append(node)
        #     continue

        assign_type = get_assign_type(node)
        _stmts, done = _get_filtered_stmts(assign_type, 
            base_node, # base node = lookup node
            node, # the LocalsAssignT node where the node to filter was assigned
            _stmts, # the already filtered statements (empty list on the first iteration)
            mystmt # the statement of the base node
            )
        
        if done:
            break

        optional_assign = optionally_assigns(assign_type)
        if optional_assign and assign_type.parent_of(base_node):
            # we are inside a loop, loop var assignment is hiding previous
            # assignment
            _stmts = [node]
            _stmt_parents = [stmt.parent]
            continue

        if isinstance(assign_type, ast.NamedExpr):
            # If the NamedExpr is in an if statement we do some basic control flow inference
            if_parent = get_if_statement_ancestor(assign_type)
            if if_parent:
                # If the if statement is within another if statement we append the node
                # to possible statements
                if get_if_statement_ancestor(if_parent):
                    optional_assign = False
                    _stmts.append(node)
                    _stmt_parents.append(stmt.parent)
                # If the if statement is first-level and not within an orelse block
                # we know that it will be evaluated
                elif not is_orelse(if_parent):
                    _stmts = [node]
                    _stmt_parents = [stmt.parent]
                # Else we do not known enough about the control flow to be 100% certain
                # and we append to possible statements
                else:
                    _stmts.append(node)
                    _stmt_parents.append(stmt.parent)
            else:
                _stmts = [node]
                _stmt_parents = [stmt.parent]

        try:
            pindex = _stmt_parents.index(stmt.parent)
        except ValueError:
            pass
        else:
            # we got a parent index, this means the currently visited node
            # is at the same block level as a previously visited node
            if get_assign_type(_stmts[pindex]).parent_of(assign_type):
                # both statements are not at the same block level
                continue
            # if currently visited node is following previously considered
            # assignment and both are not exclusive, we can drop the
            # previous one. For instance in the following code ::
            #
            #   if a:
            #     x = 1
            #   else:
            #     x = 2
            #   print x
            #
            # we can't remove neither x = 1 nor x = 2 when looking for 'x'
            # of 'print x'; while in the following ::
            #
            #   x = 1
            #   x = 2
            #   print x
            #
            # we can remove x = 1 when we see x = 2
            #
            # moreover, on loop assignment types, assignment won't
            # necessarily be done if the loop has no iteration, so we don't
            # want to clear previous assignments if any (hence the test on
            # optional_assign)
            if not (optional_assign or are_exclusive(_stmts[pindex], node)):
                del _stmt_parents[pindex]
                del _stmts[pindex]

        # If base_node and node are exclusive, then we can ignore node
        if are_exclusive(base_node, node):
            continue

        # An AssignName node overrides previous assignments if:
        #   1. node's statement always assigns
        #   2. node and base_node are in the same block (i.e., has the same parent as base_node)
        if isinstance(node, ast.NamedExpr) or (isinstance(node, (ast.Name, ast.Attribute)) and is_assign_name(node)):
            if isinstance(stmt, ast.ExceptHandler):
                # If node's statement is an ExceptHandler, then it is the variable
                # bound to the caught exception. If base_node is not contained within
                # the exception handler block, node should override previous assignments;
                # otherwise, node should be ignored, as an exception variable
                # is local to the handler block.
                if stmt.parent_of(base_node):
                    _stmts = []
                    _stmt_parents = []
                else:
                    continue
            elif not optional_assign and mystmt and stmt.parent is mystmt.parent:
                _stmts = []
                _stmt_parents = []
        elif isinstance(node, (ast.Name, ast.Attribute)) and is_del_name(node):
            # Remove all previously stored assignments
            _stmts = []
            _stmt_parents = []
            continue
        # Add the new assignment
        _stmts.append(node)

        if isinstance(node, (ast.arguments, ast.keyword)) or isinstance( # type:ignore[unreachable]
            node.parent, (ast.arguments, ast.keyword) 
        ):
            # Special case for _stmt_parents when node is a function parameter;
            # in this case, stmt is the enclosing FunctionDef, which is what we
            # want to add to _stmt_parents, not stmt.parent. This case occurs when
            # node is an Arguments node (representing varargs or kwargs parameter),
            # and when node.parent is an Arguments node (other parameters).
            # See issue #180.
            _stmt_parents.append(stmt)
        else:
            _stmt_parents.append(stmt.parent)
    return _stmts

