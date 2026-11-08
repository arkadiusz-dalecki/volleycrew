"""Only the local Nginx listener can supply the deployment context."""

import re
from ipaddress import ip_address

from starlette.responses import PlainTextResponse


class ProxyContext:
    def __init__(self, app, enabled: bool = False):
        self.app, self.enabled = app, enabled

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.enabled:
            peer = scope.get("client", ("", 0))[0]
            try:
                local = ip_address(peer).is_loopback
            except ValueError:
                local = False
            if local:
                headers = dict(scope["headers"])
                prefix = headers.get(b"x-volleycrew-base", b"").decode("ascii", errors="replace")
                if prefix and not re.fullmatch(r"/api/hassio_ingress/[A-Za-z0-9_-]+", prefix):
                    await PlainTextResponse("Invalid proxy context", status_code=400)(
                        scope, receive, send
                    )
                    return
                scope = dict(scope)
                scope["root_path"] = prefix
                # The proxy strips the prefix. Starlette routes expect it in scope.path.
                scope["path"] = prefix + scope["path"]
                proto = headers.get(b"x-forwarded-proto")
                if proto in (b"https", b"http"):
                    scope["scheme"] = proto.decode()
        await self.app(scope, receive, send)
