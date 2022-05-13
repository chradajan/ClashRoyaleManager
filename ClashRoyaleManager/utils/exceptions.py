"""Custom exceptions."""

class GeneralAPIError(Exception):
    """Raised when an API request returns a status code that is not 200 or 404."""
    pass

class ResourceNotFound(Exception):
    """Raised when resource not found by Clash Royale API."""
    pass
