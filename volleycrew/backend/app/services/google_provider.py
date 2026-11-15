"""Google OIDC code exchange and ID-token verification; no Google tokens are persisted."""

import asyncio
import base64
import hashlib
import hmac
import re
import time

import httpx
import jwt
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.client import OAuth2Client
from authlib.oauth2.rfc6749.errors import OAuth2Error

from app.core.config import Settings
from app.core.security import token_hash

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
CALLBACK_PATH = "/api/v1/auth/google/callback"


class GoogleRejected(Exception):
    pass


class GoogleUnavailable(Exception):
    pass


class GoogleProvider:
    def __init__(self, settings: Settings, key: bytes, transport=None, timer=time.monotonic):
        self.settings, self.key, self.transport = settings, key, transport
        self.timer = timer
        self._keys_ttl = 300
        self._keys: list[dict] = []
        self._keys_at = float("-inf")
        self._key_lock = asyncio.Lock()

    @property
    def callback_url(self) -> str:
        return self.settings.public_url + CALLBACK_PATH

    def verifier(self, state: str) -> str:
        value = hmac.new(self.key, f"google-pkce:{state}".encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    def client(self) -> AsyncOAuth2Client:
        return AsyncOAuth2Client(
            self.settings.google_client_id,
            self.settings.google_client_secret.get_secret_value(),
            scope="openid",
            redirect_uri=self.callback_url,
            code_challenge_method="S256",
            token_endpoint_auth_method="client_secret_post",
            transport=self.transport,
            timeout=8,
            trust_env=False,
            follow_redirects=False,
        )

    def authorization_url(self, state: str, nonce: str) -> str:
        # URL construction does not perform I/O or hold an HTTP connection.
        client = OAuth2Client(
            session=None,
            client_id=self.settings.google_client_id,
            scope="openid",
            redirect_uri=self.callback_url,
            code_challenge_method="S256",
        )
        url, _ = client.create_authorization_url(
            AUTHORIZE_URL,
            state=state,
            nonce=nonce,
            code_verifier=self.verifier(state),
            prompt="select_account",
        )
        return url

    async def keys(self, kid: str) -> list[dict]:
        async with self._key_lock:
            age = self.timer() - self._keys_at
            if age < self._keys_ttl and (any(k.get("kid") == kid for k in self._keys) or age < 30):
                return self._keys
            try:
                async with httpx.AsyncClient(
                    timeout=8, trust_env=False, transport=self.transport
                ) as client:
                    response = await client.get(JWKS_URL)
                    response.raise_for_status()
                    keys = response.json()["keys"]
                if (
                    not isinstance(keys, list)
                    or not keys
                    or len(keys) > 50
                    or not all(isinstance(key, dict) for key in keys)
                ):
                    raise ValueError()
                control = response.headers.get("cache-control", "").lower()
                age_hint = re.search(r'max-age\s*=\s*"?(\d+)', control)
                self._keys_ttl = min(300, int(age_hint[1])) if age_hint else 300
                if "no-store" in control or "no-cache" in control:
                    self._keys_ttl = 0
                self._keys, self._keys_at = keys, self.timer()
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                raise GoogleUnavailable() from None
            return self._keys

    async def verify(self, encoded: str, nonce_hash: str) -> str:
        try:
            if not isinstance(encoded, str) or len(encoded) > 16384:
                raise GoogleRejected()
            header = jwt.get_unverified_header(encoded)
            kid = header.get("kid")
            if header.get("alg") != "RS256" or not isinstance(kid, str) or len(kid) > 255:
                raise GoogleRejected()
            key = next((key for key in await self.keys(kid) if key.get("kid") == kid), None)
            if not key:
                raise GoogleRejected()
            claims = jwt.decode(
                encoded,
                jwt.PyJWK.from_dict(key, algorithm="RS256").key,
                algorithms=["RS256"],
                audience=self.settings.google_client_id,
                issuer=["https://accounts.google.com", "accounts.google.com"],
                options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
                leeway=30,
            )
            audiences = claims["aud"]
            if ("azp" in claims and claims["azp"] != self.settings.google_client_id) or (
                isinstance(audiences, list)
                and len(audiences) > 1
                and claims.get("azp") != self.settings.google_client_id
            ):
                raise GoogleRejected()
            nonce, subject = claims["nonce"], claims["sub"]
            if not isinstance(nonce, str) or not hmac.compare_digest(token_hash(nonce), nonce_hash):
                raise GoogleRejected()
            if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
                raise GoogleRejected()
            return subject
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            raise GoogleRejected() from None

    async def exchange(self, code: str, state: str, nonce_hash: str) -> str:
        try:
            async with self.client() as client:
                token = await client.fetch_token(
                    TOKEN_URL,
                    code=code,
                    code_verifier=self.verifier(state),
                    grant_type="authorization_code",
                )
            encoded = token.get("id_token")
            if not encoded:
                raise GoogleRejected()
        except (httpx.HTTPError, OAuthError, OAuth2Error, ValueError, KeyError, TypeError):
            raise GoogleUnavailable() from None
        return await self.verify(encoded, nonce_hash)
