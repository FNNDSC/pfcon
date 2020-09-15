"""
Defines a few named exceptions for marking removed legacy code.
"""

class LegacyCodeException(Exception):
    """
    Placeholder exception to throw where-ever legacy code
    seems to be doing something useless.
    """
    pass


class MismanagedStateException(LegacyCodeException):
    """
    An exception denoting that consistent state was not
    enforced by legacy code.
    """
    pass


class DeprecatedLegacyCodeException(LegacyCodeException):
    """
    For deprecated functions.
    """
    pass
