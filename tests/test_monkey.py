# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.monkey}.
"""

import ast
import inspect
import sys
from typing import Type

import unittest

from astuce._monkey import MonkeyPatcher

class NotATestCase_TestObj:
    def __init__(self):
        self.foo = "foo value"
        self.bar = "bar value"
        self.baz = "baz value"

class MonkeyPatcherTests(unittest.TestCase):
    """
    Tests for L{MonkeyPatcher} monkey-patching class.
    """

    def setUp(self):
        self.testObject = NotATestCase_TestObj()
        self.originalObject = NotATestCase_TestObj()
        self.monkeyPatcher = MonkeyPatcher()

    def test_empty(self):
        """
        A monkey patcher without patches shouldn't change a thing.
        """
        self.monkeyPatcher.patch()

        # We can't assert that all state is unchanged, but at least we can
        # check our test object.
        self.assertEqual(self.originalObject.foo, self.testObject.foo)
        self.assertEqual(self.originalObject.bar, self.testObject.bar)
        self.assertEqual(self.originalObject.baz, self.testObject.baz)

    def test_constructWithPatches(self):
        """
        Constructing a L{MonkeyPatcher} with patches should add all of the
        given patches to the patch list.
        """
        patcher = MonkeyPatcher(
            (self.testObject, "foo", "haha"), (self.testObject, "bar", "hehe")
        )
        patcher.patch()
        self.assertEqual("haha", self.testObject.foo)
        self.assertEqual("hehe", self.testObject.bar)
        self.assertEqual(self.originalObject.baz, self.testObject.baz)

    def test_patchExisting(self):
        """
        Patching an attribute that exists sets it to the value defined in the
        patch.
        """
        self.monkeyPatcher.addPatch(self.testObject, "foo", "haha")
        self.monkeyPatcher.patch()
        self.assertEqual(self.testObject.foo, "haha")

    def test_patchNonExisting(self):
        """
        Patching a non-existing attribute fails with an C{AttributeError}.
        """
        self.monkeyPatcher.addPatch(self.testObject, "nowhere", "blow up please")
        self.assertRaises(AttributeError, self.monkeyPatcher.patch)

    def test_patchAlreadyPatched(self):
        """
        Adding a patch for an object and attribute that already have a patch
        overrides the existing patch.
        """
        self.monkeyPatcher.addPatch(self.testObject, "foo", "blah")
        self.monkeyPatcher.addPatch(self.testObject, "foo", "BLAH")
        self.monkeyPatcher.patch()
        self.assertEqual(self.testObject.foo, "BLAH")
        self.monkeyPatcher.restore()
        self.assertEqual(self.testObject.foo, self.originalObject.foo)

    def test_restoreTwiceIsANoOp(self):
        """
        Restoring an already-restored monkey patch is a no-op.
        """
        self.monkeyPatcher.addPatch(self.testObject, "foo", "blah")
        self.monkeyPatcher.patch()
        self.monkeyPatcher.restore()
        self.assertEqual(self.testObject.foo, self.originalObject.foo)
        self.monkeyPatcher.restore()
        self.assertEqual(self.testObject.foo, self.originalObject.foo)

    def test_runWithPatchesDecoration(self):
        """
        runWithPatches should run the given callable, passing in all arguments
        and keyword arguments, and return the return value of the callable.
        """
        log = []

        def f(a, b, c=None):
            log.append((a, b, c))
            return "foo"

        result = self.monkeyPatcher.runWithPatches(f, 1, 2, c=10)
        self.assertEqual("foo", result)
        self.assertEqual([(1, 2, 10)], log)

    def test_repeatedRunWithPatches(self):
        """
        We should be able to call the same function with runWithPatches more
        than once. All patches should apply for each call.
        """

        def f():
            return (self.testObject.foo, self.testObject.bar, self.testObject.baz)

        self.monkeyPatcher.addPatch(self.testObject, "foo", "haha")
        result = self.monkeyPatcher.runWithPatches(f)
        self.assertEqual(
            ("haha", self.originalObject.bar, self.originalObject.baz), result
        )
        result = self.monkeyPatcher.runWithPatches(f)
        self.assertEqual(
            ("haha", self.originalObject.bar, self.originalObject.baz), result
        )

    def test_runWithPatchesRestores(self):
        """
        C{runWithPatches} should restore the original values after the function
        has executed.
        """
        self.monkeyPatcher.addPatch(self.testObject, "foo", "haha")
        self.assertEqual(self.originalObject.foo, self.testObject.foo)
        self.monkeyPatcher.runWithPatches(lambda: None)
        self.assertEqual(self.originalObject.foo, self.testObject.foo)

    def test_runWithPatchesRestoresOnException(self):
        """
        Test runWithPatches restores the original values even when the function
        raises an exception.
        """

        def _():
            self.assertEqual(self.testObject.foo, "haha")
            self.assertEqual(self.testObject.bar, "blahblah")
            raise RuntimeError("Something went wrong!")

        self.monkeyPatcher.addPatch(self.testObject, "foo", "haha")
        self.monkeyPatcher.addPatch(self.testObject, "bar", "blahblah")

        self.assertRaises(RuntimeError, self.monkeyPatcher.runWithPatches, _)
        self.assertEqual(self.testObject.foo, self.originalObject.foo)
        self.assertEqual(self.testObject.bar, self.originalObject.bar)

class Node:
    ...
class Instance:
    ...

class mod:
    class AST(ast.AST):
        ...
    class List(ast.List):
        ...
    var = 1

def copy_class(cls:Type) -> Type:
    # https://stackoverflow.com/a/37668516
    source = inspect.getsource(cls)
    globs = {}
    globs.update(sys.modules[cls.__module__].__dict__)
    exec(source, globs)
    return globs[cls.__name__]

class MonkeyPatcherMixinTests(unittest.TestCase):

    def setUp(self):
        self.mod = copy_class(mod)
        self.monkeyPatcher = MonkeyPatcher()

    def test_addMixinPatch(self):
        self.monkeyPatcher.addMixinPatch(
            self.mod, 'AST', [Node]
        )

        def check():
            assert len(self.mod.AST.__bases__)==2
            assert issubclass(self.mod.AST, Node)
        
        self.monkeyPatcher.runWithPatches(check)
        assert not issubclass(self.mod.AST, Node)
    
    def test_addMixinPatch_Multiple(self):
        original_List = self.mod.List
        self.monkeyPatcher.addMixinPatch(
            self.mod, 'List', [Node, Instance]
        )

        def check():
            assert len(self.mod.List.__bases__)==3
            assert issubclass(self.mod.List, Node)
            assert issubclass(self.mod.List, Instance)
            instance = self.mod.List()
            assert isinstance(instance, original_List)
            assert isinstance(instance, Node)
            assert isinstance(instance, Instance)
        
        self.monkeyPatcher.runWithPatches(check)
        assert not issubclass(self.mod.List, Node)
        assert not issubclass(self.mod.List, Instance)
    
    def test_addMixinPatch_Successive_Calls(self):
        self.monkeyPatcher.addMixinPatch(
            self.mod, 'List', [Instance]
        )
        self.monkeyPatcher.addMixinPatch(
            self.mod, 'List', [Node]
        )

        def check():
            assert len(self.mod.List.__bases__)==2
            assert issubclass(self.mod.List, Node)
            assert not issubclass(self.mod.List, Instance)
        
        self.monkeyPatcher.runWithPatches(check)
        assert not issubclass(self.mod.List, Node)
        assert not issubclass(self.mod.List, Instance)

    def test_addMixinPatch_Errors(self):
        self.assertRaises(AttributeError, lambda: self.monkeyPatcher.addMixinPatch(self.mod, 'notfound', [Node]))
        self.assertRaises(TypeError, lambda: self.monkeyPatcher.addMixinPatch(self.mod, 'var', [Node]))
