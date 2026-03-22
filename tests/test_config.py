import importlib.util
from pathlib import Path
import sys

import pytest


@pytest.fixture
def reload_config(monkeypatch):
    def _reload(**env):
        defaults = {
            "TRADING_MODE": "demo",
            "OPENAI_API_KEY": "test-openai-key",
            "TAVILY_API_KEY": "test-tavily-key",
            "CAPITAL_INR": "1000000",
            "GROWW_API_KEY": "test-groww-api-key",
            "GROWW_TOTP_SECRET": "test-groww-totp-secret",
        }
        defaults.update(env)

        for key, value in defaults.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

        sys.modules.pop("config", None)
        config_path = Path(__file__).resolve().parents[1] / "config.py"
        spec = importlib.util.spec_from_file_location("config", config_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["config"] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    return _reload


@pytest.mark.parametrize(
    ("missing_key", "expected_warning"),
    [
        ("GROWW_API_KEY", "GROWW_API_KEY not set in .env"),
        ("GROWW_TOTP_SECRET", "GROWW_TOTP_SECRET not set in .env"),
    ],
)
def test_validate_config_warns_for_missing_groww_env_vars_without_name_error(
    reload_config,
    missing_key,
    expected_warning,
):
    config = reload_config(**{missing_key: None})

    try:
        warnings = config.validate_config()
    except NameError as exc:  # pragma: no cover - explicit regression guard
        pytest.fail(f"validate_config() raised NameError: {exc}")

    assert expected_warning in warnings
