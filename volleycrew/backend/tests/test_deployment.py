import json
import tarfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.backup import restore
from app.core.config import Settings
from app.core.security import cookie_name, source_address
from app.deployment import Options, prepare
from app.main import create_app

NGINX = Path(__file__).resolve().parents[2] / "rootfs/etc/nginx"


def options(**changes):
    return Options.model_validate(
        {
            "POSTGRES_HOST": "db",
            "POSTGRES_PASSWORD": "a@/:$'\\secret",
            "PUBLIC_URL": "https://volleycrew.test",
            **changes,
        }
    )


def test_options_encode_password_and_reject_unsafe_values(tmp_path):
    opts = options()
    url = make_url(opts.settings(tmp_path).database_url.get_secret_value())
    assert url.password == opts.POSTGRES_PASSWORD.get_secret_value()
    for changes in [
        {"PUBLIC_URL": "http://public.example"},
        {"PUBLIC_URL": "https://public.example/path"},
        {"POSTGRES_SSL": "bogus"},
        {"TRUSTED_PROXY_CIDRS": ["0.0.0.0/0"]},
        {"TRUSTED_PROXY_CIDRS": ["127.0.0.1; include /tmp/file;"]},
        {"BOOTSTRAP_TOKEN": "short"},
        {"BOOTSTRAP_TOKEN": "x" * 32 + '"'},
        {"SESSION_SECRET": "x" * 31},
        {"ADDITIONAL_ORIGINS": ["https://ha.test/path"]},
    ]:
        with pytest.raises((ValidationError, ValueError)):
            options(**changes).settings(tmp_path)


def test_prepare_writes_private_environment_without_eval(tmp_path):
    nginx = tmp_path / "nginx"
    nginx.mkdir()
    (nginx / "nginx.conf.template").write_bytes((NGINX / "nginx.conf.template").read_bytes())
    file = tmp_path / "options.json"
    file.write_text(options(TRUSTED_PROXY_CIDRS=["172.30.33.5/32"]).model_dump_json())
    # SecretStr JSON masks values, so use a real fixture secret explicitly.
    value = json.loads(file.read_text())
    value["POSTGRES_PASSWORD"] = "literal$(never-execute)@:/"
    value["SESSION_SECRET"] = ""
    value["BOOTSTRAP_TOKEN"] = ""
    file.write_text(json.dumps(value))
    env = tmp_path / "env"
    prepare(file, tmp_path, env, nginx)
    target = env / "VOLLEYCREW_DATABASE_URL"
    assert target.stat().st_mode & 0o777 == 0o600
    assert make_url(target.read_text()).password == value["POSTGRES_PASSWORD"]
    assert not (env / "VOLLEYCREW_SESSION_SECRET").exists()
    assert "172.30.33.5/32 1;" in (nginx / "nginx.conf").read_text()
    assert "set_real_ip_from 172.30.33.5/32;" in (nginx / "nginx.conf").read_text()


def test_proxy_context_and_cookie_isolation(tmp_path):
    settings = Settings(
        _env_file=None,
        public_url="https://volleycrew.test",
        state_dir=tmp_path,
        behind_proxy=True,
        trusted_proxy_cidrs=["127.0.0.1/32"],
    )
    app = create_app(settings)

    @app.get("/api/v1/context-test")
    def context(request: Request):
        return {
            "base": request.scope["root_path"],
            "scheme": request.url.scheme,
            "session": cookie_name(request, "vc_session"),
            "source": source_address(request),
        }

    with TestClient(app, client=("127.0.0.1", 12)) as client:
        headers = {
            "X-Volleycrew-Base": "/api/hassio_ingress/dynamic_token",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "192.0.2.4",
        }
        result = client.get("/api/v1/context-test", headers=headers)
        assert result.json() == {
            "base": headers["X-Volleycrew-Base"],
            "scheme": "https",
            "session": "vc_session_ingress",
            "source": "192.0.2.4",
        }
        csrf = client.get("/api/v1/auth/csrf", headers=headers)
        cookie = csrf.headers["set-cookie"]
        assert "vc_csrf_ingress=" in cookie and "Path=/api/hassio_ingress/dynamic_token/" in cookie
        assert "Secure" in cookie and "SameSite=lax" in cookie
        direct = client.get("/api/v1/auth/csrf")
        assert "vc_csrf=" in direct.headers["set-cookie"]
        assert "Path=/;" in direct.headers["set-cookie"]
        assert (
            client.get("/api/v1/context-test", headers={"X-Volleycrew-Base": "/evil"}).status_code
            == 400
        )
    with TestClient(app, client=("192.0.2.10", 12)) as client:
        result = client.get("/api/v1/context-test", headers=headers)
        assert result.json() == {
            "base": "",
            "scheme": "http",
            "session": "vc_session",
            "source": "192.0.2.10",
        }


def test_restore_rejects_overwrite_and_unsafe_archive(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, state_dir=tmp_path)
    monkeypatch.setattr("app.backup.sql", lambda *args: "1")
    with pytest.raises(ValueError, match="not empty"):
        restore(settings, tmp_path / "missing", confirm_empty=True)
    with pytest.raises(ValueError, match="confirm-empty"):
        restore(settings, tmp_path / "missing", confirm_empty=False)
    monkeypatch.setattr("app.backup.sql", lambda *args: "0")
    bundle = tmp_path / "evil.tar.gz"
    with tarfile.open(bundle, "w:gz") as tar:
        info = tarfile.TarInfo("../overwritten")
        info.size = 3
        tar.addfile(info, BytesIO(b"bad"))
    with pytest.raises(ValueError, match="Invalid backup member"):
        restore(settings, bundle, confirm_empty=True)
    assert not (tmp_path.parent / "overwritten").exists()


def test_production_logging_discards_exception_values():
    import logging

    from app.safe_logging import ExceptionTypeOnly

    exc = ValueError("sensitive-database-password")
    record = logging.LogRecord(
        "uvicorn.error",
        logging.ERROR,
        "",
        1,
        "Exception for a credential request",
        (),
        (ValueError, exc, None),
    )
    ExceptionTypeOnly().filter(record)
    assert record.getMessage() == "Service exception (ValueError)"
    assert record.exc_info is None and record.exc_text is None


def test_home_assistant_manifest_keeps_private_listener_and_local_build():
    import yaml

    root = Path(__file__).resolve().parents[2]
    manifest = yaml.safe_load((root / "config.yaml").read_text())
    bases = yaml.safe_load((root / "build.yaml").read_text())["build_from"]
    assert set(manifest["arch"]) == {"amd64", "aarch64"}
    assert "image" not in manifest
    assert manifest["init"] is False and manifest["host_network"] is False
    assert manifest["homeassistant_api"] is False and manifest["hassio_api"] is False
    assert manifest["ports"] == {"8200/tcp": 8200}
    assert manifest["ingress_port"] == 8099 and "8099/tcp" not in manifest["ports"]
    assert manifest["schema"]["BOOTSTRAP_TOKEN"] == "password"
    assert manifest["backup_pre"] == "/usr/local/bin/volleycrew-backup create"
    assert all("@sha256:" in bases[arch] for arch in manifest["arch"])


def test_backup_hook_environment_keeps_explicit_restore_target(tmp_path, monkeypatch):
    from app.deployment import load_environment

    (tmp_path / "VOLLEYCREW_DATABASE_URL").write_text("postgresql+asyncpg://u:pw@source/source")
    (tmp_path / "VOLLEYCREW_RESTORE_DATABASE_URL").write_text("must-not-override-explicit")
    monkeypatch.delenv("VOLLEYCREW_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "VOLLEYCREW_RESTORE_DATABASE_URL", "postgresql+asyncpg://u:pw@target/restore"
    )
    load_environment(tmp_path)
    import os

    assert "@source/source" in os.environ["VOLLEYCREW_DATABASE_URL"]
    assert os.environ["VOLLEYCREW_RESTORE_DATABASE_URL"].endswith("@target/restore")
    monkeypatch.delenv("VOLLEYCREW_DATABASE_URL")
