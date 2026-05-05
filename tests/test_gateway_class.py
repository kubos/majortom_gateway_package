import pytest
from majortom_gateway import GatewayAPI
import logging

def test_logging_output():
    # A simple test to see what output is being captured
    logging.debug("DEBUG: Testing")
    logging.info("INFO: Testing")
    logging.warning("WARN: Testing")
    logging.error("ERROR: Testing")
    print("PRINT: Testing")

def test_required_args():
    with pytest.raises(TypeError):
        gw = GatewayAPI()


def test_file_exceptions_catchable_as_runtime_error():
    """FileDownloadError and FileUploadError should be catchable as RuntimeError for backward compat."""
    from majortom_gateway.exceptions import FileDownloadError, FileUploadError, FileTransferError

    with pytest.raises(RuntimeError):
        raise FileDownloadError("download failed")

    with pytest.raises(RuntimeError):
        raise FileUploadError("upload failed")

    with pytest.raises(RuntimeError):
        raise FileTransferError("transfer failed")
