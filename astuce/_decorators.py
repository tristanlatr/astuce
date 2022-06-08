# #########################     LICENSE     ############################ #

# Copyright (c) 2005-2021, Michele Simionato
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:

#   Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#   Redistributions in bytecode form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in
#   the documentation and/or other materials provided with the
#   distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDERS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.

"""
Decorator module, see
https://github.com/micheles/decorator/blob/master/docs/documentation.md
for the documentation.
"""
import re
import inspect
from inspect import iscoroutinefunction, isgeneratorfunction

__version__ = '5.1.1'

DEF = re.compile(r'\s*def\s*([_\w][_\w\d]*)\s*\(')
POS = inspect.Parameter.POSITIONAL_OR_KEYWORD
EMPTY = inspect.Parameter.empty

__all__ = ['decorator']

def fix(args, kwargs, sig):
    """
    Fix args and kwargs to be consistent with the signature
    """
    ba = sig.bind(*args, **kwargs)
    ba.apply_defaults()  # needed for test_dan_schult
    return ba.args, ba.kwargs


def decorate(func, caller, extras=(), kwsyntax=False):
    """
    Decorates a function/generator/coroutine using a caller.
    If kwsyntax is True calling the decorated functions with keyword
    syntax will pass the named arguments inside the ``kw`` dictionary,
    even if such argument are positional, similarly to what functools.wraps
    does. By default kwsyntax is False and the the arguments are untouched.
    """
    sig = inspect.signature(func)
    if iscoroutinefunction(caller):
        async def fun(*args, **kw):
            if not kwsyntax:
                args, kw = fix(args, kw, sig)
            return await caller(func, *(extras + args), **kw)
    elif isgeneratorfunction(caller):
        def fun(*args, **kw):
            if not kwsyntax:
                args, kw = fix(args, kw, sig)
            for res in caller(func, *(extras + args), **kw):
                yield res
    else:
        def fun(*args, **kw):
            if not kwsyntax:
                args, kw = fix(args, kw, sig)
            return caller(func, *(extras + args), **kw)
    fun.__name__ = func.__name__
    fun.__doc__ = func.__doc__
    fun.__wrapped__ = func
    fun.__signature__ = sig
    fun.__qualname__ = func.__qualname__
    # builtin functions like defaultdict.__setitem__ lack many attributes
    try:
        fun.__defaults__ = func.__defaults__
    except AttributeError:
        pass
    try:
        fun.__kwdefaults__ = func.__kwdefaults__
    except AttributeError:
        pass
    try:
        fun.__annotations__ = func.__annotations__
    except AttributeError:
        pass
    try:
        fun.__module__ = func.__module__
    except AttributeError:
        pass
    try:
        fun.__dict__.update(func.__dict__)
    except AttributeError:
        pass
    return fun


def decorator(caller, _func=None, kwsyntax=False):
    """
    decorator(caller) converts a caller function into a decorator
    """
    if _func is not None:  # return a decorated function
        # this is obsolete behavior; you should use decorate instead
        return decorate(_func, caller, (), kwsyntax)
    # else return a decorator function
    sig = inspect.signature(caller)
    dec_params = [p for p in sig.parameters.values() if p.kind is POS]

    def dec(func=None, *args, **kw):
        na = len(args) + 1
        extras = args + tuple(kw.get(p.name, p.default)
                              for p in dec_params[na:]
                              if p.default is not EMPTY)
        if func is None:
            return lambda func: decorate(func, caller, extras, kwsyntax)
        else:
            return decorate(func, caller, extras, kwsyntax)
    dec.__signature__ = sig.replace(parameters=dec_params)
    dec.__name__ = caller.__name__
    dec.__doc__ = caller.__doc__
    dec.__wrapped__ = caller
    dec.__qualname__ = caller.__qualname__
    dec.__kwdefaults__ = getattr(caller, '__kwdefaults__', None)
    dec.__dict__.update(caller.__dict__)
    return dec
