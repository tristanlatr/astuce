# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from inspect import isclass
from typing import Any, Sequence, Tuple, Type

__docformat__ = 'epytext'

class MonkeyPatcher:
    """
    Cover up attributes with new objects. Neat for monkey-patching things for
    unit-testing purposes.
    """

    def __init__(self, *patches:Tuple[Any, str, Any]) -> None:
        # List of patches to apply in (obj, name, value).
        self._patchesToApply = []
        # List of the original values for things that have been patched.
        # (obj, name, value) format.
        self._originals = []
        for patch in patches:
            self.addPatch(*patch)
    
    def addMixinPatch(self, obj:Any, name:str, bases:Sequence[Type[Any]]) -> None:
        """
        Add a patch so that the class C{name} on C{obj} will be a new type that extends 
        C{bases} when C{patch} is called or during C{runWithPatches}.
        You can restore the original values with a call to restore().

        Warning, if some want to add multiple mixins, all of them should 
        be listed in one call to L{addMixinPatch}, successive call to L{addMixinPatch}
        will result into the last pacth beeing applied only.

        @raises: AttributeError if the name is not found in C{obj}.
        @raises: TypeError if the object found is not a class.
        """
        curr_ob = getattr(obj, name)
        if not isclass(curr_ob):
            raise TypeError(f"{curr_ob!r} is not a class")
        value = type(name, (curr_ob, *bases), {})
        self.addPatch(obj, name, value)

    def addPatch(self, obj:Any, name:str, value:Any) -> None:
        """
        Add a patch so that the attribute C{name} on C{obj} will be assigned to
        C{value} when C{patch} is called or during C{runWithPatches}.
        You can restore the original values with a call to restore().
        """
        self._patchesToApply.append((obj, name, value))

    def _alreadyPatched(self, obj, name):
        """
        Has the C{name} attribute of C{obj} already been patched by this
        patcher?
        """
        for o, n, v in self._originals:
            if (o, n) == (obj, name):
                return True
        return False

    def patch(self):
        """
        Apply all of the patches that have been specified with L{addPatch}.
        Reverse this operation using L{restore}.
        """
        for obj, name, value in self._patchesToApply:
            if not self._alreadyPatched(obj, name):
                self._originals.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

    def restore(self):
        """
        Restore all original values to any patched objects.
        """
        while self._originals:
            obj, name, value = self._originals.pop()
            setattr(obj, name, value)

    def runWithPatches(self, f, *args, **kw):
        """
        Apply each patch already specified. Then run the function f with the
        given args and kwargs. Restore everything when done.
        """
        self.patch()
        try:
            return f(*args, **kw)
        finally:
            self.restore()
