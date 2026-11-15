"""Disposable browser-test app; excluded from the production image, never enabled by a flag."""

import base64
import hashlib
import json
import time
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.main import create_app
from app.services.google_provider import GoogleProvider

settings = get_settings()
if (
    not make_url(settings.database_url.get_secret_value()).database.endswith("_test")
    or settings.public_url != "http://127.0.0.1:5175"
    or settings.cookie_secure
    or settings.google_client_id != "browser-test.apps.googleusercontent.com"
):
    raise RuntimeError("Google browser app requires the isolated test configuration")

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
jwk.update(kid="browser-test", alg="RS256", use="sig")


def transport(request):
    if request.url.path == "/oauth2/v3/certs":
        return httpx.Response(200, json={"keys": [jwk]})
    try:
        body = parse_qs(request.content.decode())
        encoded_code = body["code"][0]
        data = json.loads(base64.urlsafe_b64decode(encoded_code + "=" * (-len(encoded_code) % 4)))
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(body["code_verifier"][0].encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        if data["challenge"] != challenge:
            raise ValueError()
        claims = {
            "iss": "https://accounts.google.com",
            "aud": settings.google_client_id,
            "sub": data["sub"],
            "nonce": data["nonce"],
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "given_name": data.get("given_name", "Google"),
            "family_name": data.get("family_name", "Testowy"),
        }
        token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "browser-test"})
        return httpx.Response(
            200, json={"id_token": token, "access_token": "discarded", "token_type": "Bearer"}
        )
    except (ValueError, KeyError, TypeError):
        return httpx.Response(400, json={"error": "invalid_grant"})


app = create_app(settings)
original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(app):
    async with original_lifespan(app):
        app.state.google_provider = GoogleProvider(
            settings, app.state.auth_key, httpx.MockTransport(transport)
        )
        yield


app.router.lifespan_context = lifespan
