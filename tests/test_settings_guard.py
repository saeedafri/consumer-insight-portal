"""The API refuses to start with settings that would make a server unsafe (api/main.check_settings)."""
import pytest

import api.main as api


@pytest.mark.parametrize("env, secret, demo, refused", [
    ("production", "x" * 64, "", False),
    ("production", "short", "", True),            # a guessable signing key
    ("production", "x" * 64, "1", True),          # the demo sign-in: anyone as anyone
    ("staging", "short", "", True),
    ("LOCAL", "short", "1", False),               # a laptop may use both
    ("production", "", "", True),                 # no key at all
])
def test_unsafe_server_settings_stop_the_api(monkeypatch, env, secret, demo, refused):
    monkeypatch.setenv("APP_ENV", env)
    monkeypatch.setenv("CIP_DEMO_LOGIN", demo)
    monkeypatch.setattr(api, "SECRET", secret.encode())
    if refused:
        with pytest.raises(RuntimeError):
            api.check_settings()
    else:
        api.check_settings()
