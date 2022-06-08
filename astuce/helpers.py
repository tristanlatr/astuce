from typing import Callable, Union, Type, Tuple, Optional, Iterator
import ast

from ._typing import ASTNode as ASTNodeT

# TODO: move me to nodenav.py
def nodes_of_class(
    self:ASTNodeT,
    klass: Union[Type[ast.AST], Tuple[Type[ast.AST], ...]],
    predicate: Optional[Callable[[ASTNodeT], bool]]=None
) -> Iterator['ASTNodeT']:
    """Get the nodes (including this one or below) of the given types.

    :param klass: The types of node to search for.
    :param predicate: Callable that returns False value to ignore more objects.

    :returns: The node of the given types.
    """
    if isinstance(self, klass):
        if predicate is not None:
            if bool(predicate(self))==True:
                yield self
        else:
            yield self

    for child_node in self.children:
        yield from nodes_of_class(child_node, klass, predicate)

