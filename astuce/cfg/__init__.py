
"""
scalpel.cfg module, patched to behave correctly.
"""

import collections
from typing import Deque, Optional, Set
from functools import reduce
from scalpel import cfg


def Link__init__(self, source, target, exitcase=None):
    assert isinstance(source, cfg.Block), "Source of a link must be a block"
    assert isinstance(target, cfg.Block), "Target of a link must be a block"
    # Block from which the control flow jump was made.
    self.source = source
    # Target block of the control flow jump.
    self.target = target
    # 'Case' leading to a control flow jump through this link.
    self.exitcase = exitcase

cfg.Link.__init__ = Link__init__

def Block_get_calls(self):
    """
    Get a string containing the calls to other functions inside the block.

    Returns:
        A string containing the names of the functions called inside the
        block.
    """
    txt = ""
    for func_call_entry in self.func_calls:
        txt += func_call_entry #patch here
        txt += '\n'
    return txt

cfg.Block.get_calls = Block_get_calls

def Block_dominates(self, other:'cfg.Block') -> bool:
    ...

def CFG_find_path(self, finalblock: 'Block') -> Deque['Link']:
    if self.entryblock is None:
        raise ValueError("entryblock cannot be none")

    assert finalblock in self.finalblocks
    visited: Set[Block] = set()
    path: Deque[Link] = collections.deque()

    def _find_path(link: Link):
        blk: Block = link.target
        if blk in visited:
            return False

        visited.add(blk)
        if blk == finalblock:
            return True

        for lk in blk.exits:
            path.append(lk)
            if _find_path(lk):
                return True
            path.pop()

    for lk in self.entryblock.exits:
        path.append(lk)
        if _find_path(lk):
            return path
        path.pop()

    # TODO find all possible paths from entry to final and return set
    # TODO find path from any line to any line
    return collections.deque()

setattr(cfg.CFG, 'find_path', CFG_find_path)

def CFG_bsearch(
        self, lineno: int, lst: Optional[list] = None
    ) -> Optional['Block']:
        """Search for a block at line"""

        def _bsearch(lst, low, high, line):
            if high >= low:
                mid = (low + high) // 2
                block = lst[mid]
                if block.at() <= line <= block.end():
                    return block
                elif line < block.at():
                    return _bsearch(lst, low, mid - 1, line)
                else:
                    return _bsearch(lst, mid + 1, high, line)
            else:
                return None

        lst = list(self) if lst is None else lst  # Already sorted by lineno
        return _bsearch(lst, 0, len(lst) - 1, lineno)

setattr(cfg.CFG, 'bsearch', CFG_bsearch)

Link = cfg.Link
Block = cfg.Block
CFG = cfg.CFG
CFGBuilder = cfg.CFGBuilder

# end of patch

# extra functions

def compute_dom_old(cfg:CFG) -> dict:
    all_blocks = cfg.get_all_blocks()
    entry_block = all_blocks[0]
    id2blocks = {b.id:b for b in all_blocks}
    block_ids = list(id2blocks.keys())
    entry_id = entry_block.id
    N_blocks = len(all_blocks)
    dom = {}
    # for all other nodes, set all nodes as the dominators
    for b_id in block_ids:
        if b_id == entry_id:
            dom[b_id] = set([entry_id])
        else:
            dom[b_id] = set(block_ids)
    # Iteratively eliminate nodes that are not dominators
    #Dom(n) = {n} union with intersection over Dom(p) for all p in pred(n)
    changed = True
    counter = 0
    while changed:
        changed = False
        for b_id in block_ids:
            if b_id == entry_id:
                continue
            pre_block_ids = [pre_link.source.id for pre_link in id2blocks[b_id].predecessors ]
            pre_dom_set = [dom[pre_b_id] for pre_b_id in pre_block_ids if pre_b_id in dom]
            new_dom_set = set([b_id])

            if len(pre_dom_set) != 0:
                new_dom_tmp = reduce(set.intersection, pre_dom_set) 
                new_dom_set = new_dom_set.union(new_dom_tmp)
            old_dom_set = dom[b_id]

            if new_dom_set != old_dom_set:
                changed = True
                dom[b_id] = new_dom_set
    return dom