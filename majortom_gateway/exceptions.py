"""
Custom exceptions for the Gateway API.
"""


class GatewayAPIError(Exception):
    """Base exception for all Gateway API errors."""
    pass


class ValidationError(GatewayAPIError):
    """Raised when invalid parameters are provided."""
    pass


class FileTransferError(GatewayAPIError):
    """Base exception for file transfer operations."""
    pass


class FileDownloadError(FileTransferError):
    """Raised when file download fails."""
    pass


class FileUploadError(FileTransferError):
    """Raised when file upload fails."""
    pass
