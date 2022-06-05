import ast
from ._typing import ASTNode as ASTNodeT, _InferMethT
from ._context import OptionalInferenceContext
from ._decorators import decorator

from . import nodes, exceptions

# Inference decorators
@decorator
def path_wrapper(func:_InferMethT, node: ASTNodeT, context: OptionalInferenceContext):
    """
    Return the given infer function wrapped to handle the path

    Used to stop inference if the node has already been looked
    at for a given `InferenceContext` to prevent infinite recursion.
    """

    """wrapper function handling context"""
    if context is None:
        try:
            context = node._parser._new_context()
        except AttributeError as e:
            # TODO: remove me 
            raise ValueError(f"Invalid node: {ast.dump(node)}") from e
    if context.push(node):
        return

    yielded = set()

    for res in func(node, context):
        # TODO: Unsued code for now for inferred instance nodes...
        # unproxy only true instance, not const, tuple, dict...
        # if res.__class__.__name__ == "Instance":
        #     ares = res._proxied
        # else:
        #     ares = res
        if res not in yielded:
            yield res
            yielded.add(res)

@decorator
def yes_if_nothing_inferred(func:_InferMethT, node: ASTNodeT, *args, **kwargs):
    """
    Return the given infer function wrapped to yield Uninferable if the generator is empty.
    """
    generator = func(node, *args, **kwargs)

    try:
        yield next(generator)
    except StopIteration:
        # generator is empty
        yield nodes.Uninferable
        return

    yield from generator

@decorator
def raise_if_nothing_inferred(func:_InferMethT, node: ASTNodeT, *args, **kwargs):
    """
    Return the given infer function wrapped to raise InferenceError if the generator is empty.
    """
    generator = func(node, *args, **kwargs)
    try:
        yield next(generator)
    except StopIteration as error:
        # generator is empty
        if error.args:
            # pylint: disable=not-a-mapping
            raise exceptions.InferenceError(**error.args[0]) from error
        raise exceptions.InferenceError(
            "StopIteration raised without any error information."
        ) from error

    yield from generator
