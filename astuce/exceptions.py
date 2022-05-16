class LastNodeError(Exception):
    """Exception raised when trying to access a next or previous node."""

class RootNodeError(Exception):
    """Exception raised when trying to use an incompatible API on a root node."""

class NameResolutionError(Exception):
    """Exception for names that cannot be resolved in a object scope."""

class StaticAnalysisWarning(Warning):
    ...
