#!/usr/bin/env python3
"""Repository task runner. Requires Python 3.9+ only to bootstrap uv."""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "volleycrew/backend"
FRONTEND = ROOT / "volleycrew/frontend"
ENV = os.environ.copy()
ENV.setdefault("UV_CACHE_DIR", str(ROOT / ".cache/uv"))
ENV.setdefault("UV_PYTHON_INSTALL_DIR", str(ROOT / ".tools/python"))
ENV.setdefault("VOLLEYCREW_ENV_FILE", str(ROOT / ".env"))
ENV.setdefault("npm_config_cache", str(ROOT / ".cache/npm"))


def uv_path():
    local = ROOT / ".tools/bin/uv"
    path = shutil.which("uv") or (str(local) if local.exists() else None)
    if not path:
        raise SystemExit("Missing uv. Run npm run setup first.")
    return path


def backend(*args):
    return [
        uv_path(),
        "run",
        "--project",
        str(BACKEND),
        "--directory",
        str(BACKEND),
        "--frozen",
        *args,
    ]


def run(args):
    subprocess.run(args, cwd=ROOT, env=ENV, check=True)


def setup():
    if not shutil.which("uv") and not (ROOT / ".tools/bin/uv").exists():
        run([sys.executable, "-m", "venv", str(ROOT / ".tools")])
        run([str(ROOT / ".tools/bin/python"), "-m", "pip", "install", "uv==0.13.7"])
    if not (ROOT / ".env").exists():
        shutil.copyfile(ROOT / ".env.example", ROOT / ".env")
    run([uv_path(), "sync", "--project", str(BACKEND), "--frozen"])
    run(["npm", "--prefix", str(FRONTEND), "ci"])


def dev():
    # Migrations are explicit and complete before the API starts serving requests.
    run(backend("alembic", "upgrade", "head"))
    ENV.setdefault(
        "VOLLEYCREW_API_PROXY", "http://127.0.0.1:" + ENV.get("VOLLEYCREW_API_PORT", "8201")
    )
    commands = [
        backend(
            "uvicorn",
            "app.main:app",
            "--reload",
            "--no-proxy-headers",
            "--host",
            ENV.get("VOLLEYCREW_API_HOST", "127.0.0.1"),
            "--port",
            ENV.get("VOLLEYCREW_API_PORT", "8201"),
        ),
        ["npm", "--prefix", str(FRONTEND), "run", "dev"],
    ]
    children = []

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        for command in commands:
            children.append(subprocess.Popen(command, cwd=ROOT, env=ENV, start_new_session=True))
        print("Volleycrew: http://localhost:5173 | API: http://127.0.0.1:8201", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.3)
        raise SystemExit(
            next(child.returncode or 1 for child in children if child.poll() is not None)
        )
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "help"
    if task == "setup":
        setup()
    elif task == "dev-preview":
        run(backend("alembic", "upgrade", "head"))
        run(backend("python", "-m", "app.seed_preview"))
        ENV["VITE_LOCAL_PREVIEW"] = "true"
        dev()
    elif task == "dev":
        dev()
    elif task == "migrate":
        run(backend("alembic", "upgrade", "head"))
    elif task == "api-server":
        run(backend("alembic", "upgrade", "head"))
        run(
            backend(
                "uvicorn",
                "app.main:app",
                "--no-proxy-headers",
                "--host",
                "127.0.0.1",
                "--port",
                ENV.get("VOLLEYCREW_API_PORT", "8201"),
            )
        )
    elif task == "e2e-reset-limits":
        run(backend("python", "-m", "tests.seed_e2e", "--reset-limits"))
    elif task == "e2e-seed":
        run(backend("python", "-m", "tests.seed_e2e"))
    elif task == "bootstrap":
        run(backend("alembic", "upgrade", "head"))
        run(backend("python", "-m", "app.manage", "create-bootstrap", *sys.argv[2:]))
    elif task == "lint":
        run(
            backend(
                "ruff", "check", "--config", str(BACKEND / "pyproject.toml"), ".", "../../scripts"
            )
        )
        run(
            backend(
                "ruff",
                "format",
                "--check",
                "--config",
                str(BACKEND / "pyproject.toml"),
                ".",
                "../../scripts",
            )
        )
    elif task == "format":
        run(
            backend(
                "ruff", "format", "--config", str(BACKEND / "pyproject.toml"), ".", "../../scripts"
            )
        )
        run(
            backend(
                "ruff",
                "check",
                "--fix",
                "--config",
                str(BACKEND / "pyproject.toml"),
                ".",
                "../../scripts",
            )
        )
    elif task == "test":
        run(backend("pytest", *sys.argv[2:]))
    elif task == "openapi":
        run(backend("python", "-m", "app.export_openapi", *sys.argv[2:]))
    else:
        raise SystemExit("Tasks: setup, dev, migrate, lint, format, test, openapi")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from None
