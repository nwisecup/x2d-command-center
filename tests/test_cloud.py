"""Cloud API parsing tests (pure functions — no network)."""
import base64
import json

import contextlib

import conftest  # noqa: F401

from bambu_x2d.cloud import NeedsTfa, NeedsVerifyCode, CloudError, parse_devices, parse_login, uid_from_token


class _Caught:
    value = None


@contextlib.contextmanager
def raises(exc_type):
    """pytest.raises stand-in that also works under the dependency-free runner."""
    caught = _Caught()
    try:
        yield caught
    except exc_type as err:
        caught.value = err
        return
    raise AssertionError(f"{exc_type.__name__} not raised")


def _jwt(payload: dict) -> str:
    seg = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJSUzI1NiJ9.{seg}.sig"


def test_parse_login_token():
    assert parse_login({"accessToken": "abc", "refreshToken": "r"}) == "abc"


def test_parse_login_verify():
    with raises(NeedsVerifyCode):
        parse_login({"loginType": "verifyCode"})


def test_parse_login_tfa():
    with raises(NeedsTfa) as err:
        parse_login({"loginType": "tfa", "tfaKey": "k123"})
    assert err.value.tfa_key == "k123"


def test_parse_login_error():
    with raises(CloudError):
        parse_login({"error": "bad credentials"})


def test_uid_from_token():
    assert uid_from_token(_jwt({"username": "u_1234567890"})) == "u_1234567890"
    assert uid_from_token("garbage") is None
    assert uid_from_token(_jwt({"other": 1})) is None


def test_parse_devices():
    payload = {"devices": [
        {"dev_id": "0409AC123", "name": "Garage X2D", "dev_access_code": "12345678",
         "dev_product_name": "X2D", "dev_online": True},
        {"dev_id": None, "name": "ghost"},
    ]}
    devs = parse_devices(payload)
    assert len(devs) == 1
    assert devs[0] == {"serial": "0409AC123", "name": "Garage X2D", "model": "X2D",
                       "access_code": "12345678", "online": True}
