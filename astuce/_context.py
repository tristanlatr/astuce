# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Like astroid's inference context utilities, but more simple.
"""
# without support for callable context or bound nodes.
from __future__ import annotations

import contextlib
import pprint
import ast

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Set, Tuple, overload
from ._typing import ASTNode as ASTNodeT

_InferenceCache = Dict[ASTNodeT, Tuple[ASTNodeT]]

class InferenceContext:
    """
    Provide context for inference.

    Store already inferred nodes to save time.
    Account for already visited nodes to stop infinite recursion.
    """

    __slots__ = (
        "path",
        "_cache",
        "_nodes_inferred",
    )

    max_inferred = 100

    def __init__(self, cache: _InferenceCache, 
        path:Optional[List['ASTNodeT']]=None, 
        nodes_inferred:Optional[List[int]]=None):
        """
        Do not instiate me directly, use copy_context() or Parser._new_context().
        """
        self._nodes_inferred: List[int]
        if nodes_inferred is None:
            self._nodes_inferred = [0]
        else:
            self._nodes_inferred = nodes_inferred

        self._cache: _InferenceCache = cache
        """
        Store cache here instead of using a global variable. 
        
        This dict is shared by all InferenceContext instances
        created by the method `parser.Parser._new_context`.

        Two different `parser.Parser` instances will use two different caches.

        More on the cache: https://github.com/PyCQA/astroid/pull/1009
        """
        
        self.path = path or list()
        """
        :type: set(NodeNG)

        List of visited nodes.
        """
        
        """
        What is this lookupname thing is anyway? 
        https://github.com/PyCQA/astroid/commit/3d342e85e127fd0f9300fbfd13666747dd9221bd
        """
        
    @property
    def nodes_inferred(self) -> int:
        """
        Number of nodes inferred in this context and all its clones/descendents

        Wrap inner value in a mutable cell to allow for mutating a class
        variable in the presence of __slots__
        """
        return self._nodes_inferred[0]

    @nodes_inferred.setter
    def nodes_inferred(self, value:int) -> None:
        self._nodes_inferred[0] = value

    @property
    def inferred(self) -> _InferenceCache:
        """
        Inferred (cached) nodes to their mapped results.
        """
        return self._cache

    def push(self, node:ASTNodeT) -> bool:
        """Push node into inference path

        :return: True if node is already in context path else False
        :rtype: bool

        Allows one to see if the given node has already
        been looked at for this inference context"""
        if node in self.path:
            return True

        self.path.append(node)
        return False

    def clone(self) -> 'InferenceContext':
        """
        Clone inference path

        For example, each side of a binary operation (BinOp)
        starts with the same context but diverge as each side is inferred
        so the InferenceContext will need be cloned
        
        :note: If a new cache is needed for this context, use `copy_context`
            with argument: ``cache={}``.
        """

        clone = InferenceContext(
            self._cache, 
            self.path.copy(), 
            nodes_inferred=self._nodes_inferred)
        
        return clone

    def __str__(self) -> str:
        state = (
            f"{field}={pprint.pformat(getattr(self, field), width=80 - len(field))}"
            for field in self.__slots__
        )
        return "{}({})".format(type(self).__name__, ",\n    ".join(state))
    

OptionalInferenceContext = Optional[InferenceContext]

@overload
def copy_context(context: None, cache: _InferenceCache) -> InferenceContext:
    ...
@overload
def copy_context(context: InferenceContext, cache: _InferenceCache | None = None, **kwargs:Any) -> InferenceContext:
    ...
def copy_context(context: InferenceContext | None, cache: _InferenceCache | None = None, **kwargs:Any) -> InferenceContext:
    """
    Clone a context if given, or return a fresh context.
    
    - If ``context`` is ``None``, ``cache`` dict must be passed.
    - If ``context`` and ``cache`` are not ``None``, override the new context cache.
    """
    if context is not None:
        ctx = context.clone()
        if cache is not None:
            ctx._cache = cache
        return ctx
    assert cache is not None
    return InferenceContext(cache=cache)
