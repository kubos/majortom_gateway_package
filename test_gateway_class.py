import pytest
from majortom_gateway import GatewayAPI


def test_required_args():
    with pytest.raises(TypeError):
        gw = GatewayAPI()
