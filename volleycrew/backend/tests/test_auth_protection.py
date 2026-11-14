import json
from types import SimpleNamespace

import pytest

from app.core.auth_protection import AuthAdmission, AuthProtection, SecurityMonitor
from app.core.config import Settings


def test_burst_gate_refills_and_is_bounded_across_sources():
    at = [0.0]
    gate = AuthAdmission(lambda: at[0])
    assert [gate.check("one") for _ in range(10)] == [0] * 10
    assert gate.check("one") == 2
    assert [gate.check("two") for _ in range(10)] == [0] * 10
    assert gate.check("three") == 1  # Global budget also covers distributed requests.
    at[0] += 2
    assert gate.check("one") == 0
    assert gate.check("one") == 2
    for index in range(2000):
        gate.check(str(index))
    assert len(gate.sources) == 1024


def test_monitor_bounds_logs_and_never_records_raw_source(caplog):
    at = [0.0]
    monitor = SecurityMonitor(b"key-a", lambda: at[0])
    with caplog.at_level("INFO", logger="volleycrew.security"):
        for _ in range(1000):
            monitor.record("auth_failed", "login", "192.0.2.1\nsecret")
        assert len(caplog.records) == 61
        assert json.loads(caplog.records[-1].message)["event"] == "security_logs_suppressed"
        assert "192.0.2.1" not in caplog.text and "secret" not in caplog.text
        first_source = json.loads(caplog.records[0].message)["source"]
        at[0] += 60
        monitor.record("auth_failed", "login", "192.0.2.1\nsecret")
        assert len(caplog.records) == 62
        assert json.loads(caplog.records[-1].message)["source"] == first_source
        SecurityMonitor(b"key-b").record("auth_failed", "login", "192.0.2.1\nsecret")
        assert json.loads(caplog.records[-1].message)["source"] != first_source


@pytest.mark.parametrize("prefix", ["", "/api/hassio_ingress/test-prefix"])
@pytest.mark.asyncio
async def test_gate_rejects_before_downstream_or_body_and_preserves_ingress(prefix):
    calls = []
    responses = []
    state = SimpleNamespace(
        settings=Settings(trusted_proxy_cidrs=["127.0.0.1/32"]),
        security_monitor=SecurityMonitor(b"test-key"),
    )

    async def downstream(scope, receive, send):
        calls.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def receive():
        raise AssertionError("Rejected request must not read its body")

    async def send(message):
        responses.append(message)

    protection = AuthProtection(downstream)
    protection.admission = AuthAdmission(lambda: 0)
    scope = {
        "type": "http",
        "method": "POST",
        "root_path": prefix,
        "path": prefix + "/api/v1/auth/login/",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"192.0.2.7")],
        "client": ("127.0.0.1", 1234),
        "app": SimpleNamespace(state=state),
    }
    for _ in range(10):
        await protection(scope, receive, send)
    responses.clear()
    await protection(scope, receive, send)
    assert len(calls) == 10
    assert responses[0]["status"] == 429
    assert dict(responses[0]["headers"])[b"retry-after"] == b"2"
    assert json.loads(responses[1]["body"])["code"] == "rate_limited"
    # Other users can still sign up for meetings and health remains reachable.
    await protection({**scope, "path": prefix + "/api/v1/meetings/resolve"}, receive, send)
    await protection(
        {**scope, "method": "GET", "path": prefix + "/api/v1/health/live"}, receive, send
    )
    assert len(calls) == 12
