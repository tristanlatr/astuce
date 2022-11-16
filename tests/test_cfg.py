
import collections
import unittest
import ast
import sys
import os
import functools
import textwrap

from astuce.cfg import Block, Link, CFGBuilder, CFG, compute_dom_old
from astuce.parser import _unparse as unparse, Parser

class TestBlock(unittest.TestCase):
    def test_instanciation(self):
        block = Block(1)
        self.assertEqual(block.id, 1)
        self.assertEqual(block.statements, [])
        self.assertEqual(block.func_calls, [])
        self.assertEqual(block.predecessors, [])
        self.assertEqual(block.exits, [])

    def test_str_representation(self):
        block = Block(1)
        self.assertEqual(str(block), "empty block:1")
        tree = ast.parse("a = 1")
        block.statements.append(tree.body[0])
        self.assertEqual(str(block), "block:1@1")

    def test_repr(self):
        block = Block(1)
        self.assertEqual(repr(block), "empty block:1 with 0 exits")
        tree = ast.parse("a = 1")
        block.statements.append(tree.body[0])
        self.assertEqual(
            repr(block),
            f"block:1@1 with 0 exits, body=[{ast.dump(tree.body[0])}]",
        )

    def test_at(self):
        block = Block(1)
        self.assertEqual(block.at(), None)
        tree = ast.parse("a = 1")
        block.statements.append(tree.body[0])
        self.assertEqual(block.at(), 1)

    def test_is_empty(self):
        block = Block(1)
        self.assertTrue(block.is_empty())
        tree = ast.parse("a = 1")
        block.statements.append(tree.body[0])
        self.assertFalse(block.is_empty())

    def test_get_source(self):
        block = Block(1)
        self.assertEqual(block.get_source(), "#1\n")
        tree = ast.parse("a = 1")
        block.statements.append(tree.body[0])
        self.assertEqual(block.get_source(), "#1\na = 1\n")

    def test_get_calls(self):
        block = Block(1)
        self.assertEqual(block.get_calls(), "")
        block.func_calls.append("fun")
        self.assertEqual(block.get_calls(), "fun\n")


class TestLink(unittest.TestCase):
    def test_instanciation(self):
        block1 = Block(1)
        block2 = Block(2)
        with self.assertRaises(AssertionError):
            Link(2, block2)  # Source of a link must be a block.
            Link(block1, 2)  # Target of a link must be a block.

        condition = ast.parse("a == 1").body[0]
        link = Link(block1, block2, condition)
        self.assertEqual(link.source, block1)
        self.assertEqual(link.target, block2)
        self.assertEqual(link.exitcase, condition)

    def test_str_representation(self):
        block1 = Block(1)
        block2 = Block(2)
        link = Link(block1, block2)
        self.assertEqual(str(link), "link from empty block:1 to empty block:2")

    def test_repr(self):
        block1 = Block(1)
        block2 = Block(2)
        condition = ast.parse("a == 1").body[0]
        link = Link(block1, block2, condition)
        self.assertEqual(
            repr(link),
            "link from empty block:1 to empty block:2, with exitcase {}".format(
                ast.dump(condition)
            ),
        )

    def test_get_exitcase(self):
        block1 = Block(1)
        block2 = Block(2)
        condition = ast.parse("a == 1").body[0]
        link = Link(block1, block2, condition)
        self.assertEqual(link.get_exitcase(), "a == 1\n")

class TestCFG(unittest.TestCase):
    def test_instanciation(self):
        with self.assertRaises(AssertionError):
            CFG(2, False)  # Name of a CFG must be a string.
            CFG("cfg", 2)  # Async argument must be a boolean.

        cfg = CFG("cfg", False)
        self.assertEqual(cfg.name, "cfg")
        self.assertFalse(cfg.asynchr)
        self.assertEqual(cfg.entryblock, None)
        self.assertEqual(cfg.finalblocks, [])
        self.assertEqual(cfg.functioncfgs, {})

    def test_str_representation(self):
        cfg = CFG("cfg", False)
        self.assertEqual(str(cfg), "CFG for cfg")

    def test_iter(self):
        src = textwrap.dedent(
            """
            def fib():
                a, b = 0, 1
                while True:
                    yield a
                    a, b = b, a + b
        """
        )
        cfg = CFGBuilder().build_from_src("fib", src)
        expected_block_sources = [
            "#1\ndef fib():...\n",
            "#3\na, b = 0, 1\n",
            "#4\nwhile True:\n",
            "#5\nyield a\n",
            "#7\na, b = b, a + b\n",
        ]
        for actual_block, expected_src in zip(cfg, expected_block_sources):
            self.assertEqual(actual_block.get_source(), expected_src)

    def test_find_path(self):
        src = textwrap.dedent("""
        def min(x, y):
            if x < y:
                return x
            elif x > y:
                return y
            else:
                return x
        """)
        cfg: CFG = CFGBuilder().build("mod", ast.parse(src)).functioncfgs[1,"min"]
        path = cfg.find_path(cfg.finalblocks[0])
        self.assertEqual(len(path), 2)
        l0_ops = path[0].exitcase.ops[0]
        l1_ops = path[1].exitcase.ops[0]
        self.assertTrue(isinstance(l0_ops, ast.GtE))
        self.assertTrue(isinstance(l1_ops, ast.LtE))
        assert unparse(path[0].exitcase) == 'x >= y'
        assert unparse(path[1].exitcase) == 'x <= y'

    def test_find_path_2(self):
        src = textwrap.dedent("""
            print('welcome')
            T = _junk = True
            assert T

            if T:
                v = True
                if T and v:
                    d = False
                else:
                    d = True
            else:
                v = False
            
            if not v or not d:
                raise RuntimeError()
        """)
        cfg: CFG = CFGBuilder().build("mod", ast.parse(src))
        dom = compute_dom_old(cfg)
        assert '\n'.join(b.get_source() for b in cfg.get_all_blocks())
            #  #1
            #  print('welcome')
            #  T = _junk = True
            #  assert T
            #  
            #  #3
            #  if T:
            #  
            #  #4
            #  v = True
            #  if T and v:
            #  
            #  #6
            #  v = False
            #  
            #  #7
            #  d = False
            #  
            #  #9
            #  d = True
            #  
            #  #5
            #  if not v or not d:
            #  
            #  #10
            #  raise RuntimeError()
        assert repr(dom) == '{1: {1}, 3: {1, 3}, 4: {1, 3, 4}, 6: {1, 3, 6}, 7: {1, 3, 4, 7}, 9: {9, 3, 4, 1}, 5: {1, 3, 5}, 10: {1, 10, 3, 5}}'
        assert len(cfg.finalblocks)==3
#         assert '\n'.join(repr(block) for block in cfg.finalblocks) == '''\
# empty block:2 with 0 exits
# block:7@10 with 0 exits, body=[Raise(exc=Call(func=Name(id='RuntimeError', ctx=Load()), args=[], keywords=[]))]
# block:13@16 with 0 exits, body=[Raise(exc=Call(func=Name(id='RuntimeError', ctx=Load()), args=[], keywords=[]))]'''
#         assert '\n'.join(repr(block) for block in cfg.get_all_blocks()) == '''\
# block:1@2 with 1 exits, body=[Expr(value=Call(func=Name(id='print', ctx=Load()), args=[Constant(value='welcome')], keywords=[])), Assert(test=Constant(value=True))]
# block:3@5 with 2 exits, body=[If(test=Constant(value=True), body=[Assign(targets=[Name(id='v', ctx=Store())], value=Constant(value=True))], orelse=[Assign(targets=[Name(id='v', ctx=Store())], value=Constant(value=False))])]
# block:4@6 with 1 exits, body=[Assign(targets=[Name(id='v', ctx=Store())], value=Constant(value=True))]
# block:6@8 with 1 exits, body=[Assign(targets=[Name(id='v', ctx=Store())], value=Constant(value=False))]
# block:5@9 with 2 exits, body=[If(test=UnaryOp(op=Not(), operand=Name(id='v', ctx=Load())), body=[Raise(exc=Call(func=Name(id='RuntimeError', ctx=Load()), args=[], keywords=[]))], orelse=[])]
# block:7@10 with 0 exits, body=[Raise(exc=Call(func=Name(id='RuntimeError', ctx=Load()), args=[], keywords=[]))]
# block:8@11 with 2 exits, body=[If(test=Constant(value=False), body=[Assign(targets=[Name(id='d', ctx=Store())], value=Constant(value=False))], orelse=[Assign(targets=[Name(id='d', ctx=Store())], value=Constant(value=True))])]
# block:10@12 with 1 exits, body=[Assign(targets=[Name(id='d', ctx=Store())], value=Constant(value=False))]
# block:12@14 with 1 exits, body=[Assign(targets=[Name(id='d', ctx=Store())], value=Constant(value=True))]
# block:11@15 with 1 exits, body=[If(test=UnaryOp(op=Not(), operand=Name(id='d', ctx=Load())), body=[Raise(exc=Call(func=Name(id='RuntimeError', ctx=Load()), args=[], keywords=[]))], orelse=[])]
# block:13@16 with 0 exits, body=[Raise(exc=Call(func=Name(id='RuntimeError', ctx=Load()), args=[], keywords=[]))]'''

        path = cfg.find_path(cfg.finalblocks[0])
        self.assertEqual(len(path), 0)
        # l0_ops = path[0].exitcase.ops[0]
        # l1_ops = path[1].exitcase.ops[0]
        # self.assertTrue(isinstance(l0_ops, ast.GtE))
        # self.assertTrue(isinstance(l1_ops, ast.LtE))
        # assert unparse(path[0].exitcase) == 'x >= y'
        # assert unparse(path[1].exitcase) == 'x <= y'


    

