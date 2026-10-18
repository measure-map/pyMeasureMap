from pymeasuremap.utils import get_m21_input_extensions


def test_get_m21_input_extensions():
    extensions = get_m21_input_extensions()
    assert ".mxl" in extensions and ".mei" in extensions
