import importlib
import os

import pytest


@pytest.fixture(autouse=True)
def restore_cwd():
    original = os.getcwd()
    yield
    os.chdir(original)


def test_resolve_prefers_explicit_path(tmp_path):
    from main import _resolve
    cert = tmp_path / "cert.pem"
    cert.write_text("explicit")
    assert _resolve(str(cert)) == str(cert)


def test_resolve_project_cert_falls_back_to_app_support(tmp_path, monkeypatch):
    """When the project-relative 'certs/cert.pem' doesn't exist but its
    app-support equivalent does, return the app-support one."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    support_dir = tmp_path / "support"
    monkeypatch.setenv("MACAPI_HOME", str(support_dir))
    importlib.reload(importlib.import_module("main"))
    from main import _resolve

    support_cert = support_dir / "certs" / "cert.pem"
    support_cert.parent.mkdir(parents=True)
    support_cert.write_text("in support dir")

    os.chdir(project_dir)
    result = _resolve("certs/cert.pem")
    assert result == str(support_cert)


def test_resolve_project_key_falls_back_to_app_support(tmp_path, monkeypatch):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    support_dir = tmp_path / "support"
    monkeypatch.setenv("MACAPI_HOME", str(support_dir))
    importlib.reload(importlib.import_module("main"))
    from main import _resolve

    support_key = support_dir / "certs" / "key.pem"
    support_key.parent.mkdir(parents=True)
    support_key.write_text("k")

    os.chdir(project_dir)
    result = _resolve("certs/key.pem")
    assert result == str(support_key)


def test_resolve_env_file_falls_back_to_config_env(tmp_path, monkeypatch):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    support_dir = tmp_path / "support"
    monkeypatch.setenv("MACAPI_HOME", str(support_dir))
    importlib.reload(importlib.import_module("main"))
    from main import _resolve

    support_env = support_dir / "config.env"
    support_dir.mkdir(parents=True, exist_ok=True)
    support_env.write_text("OWNER_TOKEN=x\n")

    os.chdir(project_dir)
    result = _resolve(".env")
    assert result == str(support_env)


def test_resolve_returns_input_path_if_nothing_exists(tmp_path, monkeypatch):
    """Arbitrary path that's not a project-relative default: returned as-is."""
    monkeypatch.setenv("MACAPI_HOME", str(tmp_path))
    importlib.reload(importlib.import_module("main"))
    from main import _resolve

    arbitrary = "/some/random/path/that/does/not/exist"
    assert _resolve(arbitrary) == arbitrary
