class StaticAnalysisException(Exception):
    """base exception class for all astuce related exceptions

    StaticAnalysisException and its subclasses are structured, intended to hold
    objects representing state when the exception is thrown.  Field
    values are passed to the constructor as keyword-only arguments.
    Each subclass has its own set of standard fields, but use your
    best judgment to decide whether a specific exception instance
    needs more or fewer fields for debugging.  Field values may be
    used to lazily generate the error message: self.message.format()
    will be called with the field names and values supplied as keyword
    arguments.
    """

    def __init__(self, message="", **kws):
        super().__init__(message)
        self.message = message
        for key, value in kws.items():
            setattr(self, key, value)

    def __str__(self):
        return self.message.format(**vars(self))

class LastNodeError(StaticAnalysisException):
    """Exception raised when trying to access a next or previous node."""

class RootNodeError(StaticAnalysisException):
    """Exception raised when trying to use an incompatible API on a root node."""

class NameResolutionError(StaticAnalysisException):
    """Exception for names that cannot be resolved in a object scope."""

class ResolveError(StaticAnalysisException):
    """Base class of astroid resolution/inference error.

    ResolveError is not intended to be raised.

    Standard attributes:
        context: InferenceContext object.
    """

    context = None


class InferenceError(ResolveError):
    """raised when we are unable to infer a node

    Standard attributes:
        node: The node inference was called on.
        context: InferenceContext object.
    """

    node = None
    context = None

    def __init__(self, message="Inference failed for {node!r}.", **kws):
        super().__init__(message, **kws)


class NameInferenceError(InferenceError):
    """Raised when a name lookup fails, corresponds to NameError.

    Standard attributes:
        name: The name for which lookup failed, as a string.
        scope: The node representing the scope in which the lookup occurred.
        context: InferenceContext object.
    """

    name = None
    scope = None

    def __init__(self, message="{name!r} not found in {scope!r}.", **kws):
        super().__init__(message, **kws)

# This class does not inherit InferenceError because it's the way astroid's exceptions are designed. 
# We might add code tht relies on AttributeInferenceError not beeing caught by InferenceError handlers.
class AttributeInferenceError(ResolveError):
    """Raised when an attribute lookup fails, corresponds to AttributeError.

    Standard attributes:
        target: The node for which lookup failed.
        attribute: The attribute for which lookup failed, as a string.
        context: InferenceContext object.
    """

    target = None
    attribute = None

    def __init__(self, message="{attribute!r} not found on {target!r}.", **kws):
        super().__init__(message, **kws)


class StaticAnalysisWarning(Warning):
    ...

class TooManyLevelsError(StaticAnalysisWarning):
    """
    Warning class which is used when a relative import was beyond the top-level.
    """
