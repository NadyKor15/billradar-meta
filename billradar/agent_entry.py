"""The entry for AI agents: one ASGI app with the MCP server, the A2A agent and its card.

  POST /mcp                          MCP, Streamable HTTP, stateless (spec 2026-07-28)
  GET  /.well-known/agent-card.json  A2A agent card (protocol 1.0)
  POST /a2a                          A2A JSON-RPC (SendMessage)
  GET  /agents/healthz

The web app mounts it at the root, after its own routes, so the card sits at the well-known path.

Access (decided 27.10): the fictional sample packs are open without a key, limited per address;
an X-API-Key (kept in the vault, never published) is needed only for an agent's own papers, which
also need a live model. A wrong key is refused, not treated as anonymous. With live runs switched on
and no keys configured, the app refuses to start.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque

from mcp.server.transport_security import TransportSecuritySettings
from pathlib import Path

from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from billradar import a2a_agent, agent_api, mail_intake, mcp_server, providers

MAX_BODY = 64 * 1024 * 1024


def _keys() -> set[str]:
    return {k.strip() for k in os.environ.get("BILLRADAR_AGENT_KEYS", "").split(",") if len(k.strip()) >= 24}


class Gate:
    """Pure ASGI (tool answers may stream as SSE): API key, a per-address limit for anonymous calls,
    and a cap on the request size."""

    def __init__(self, app, keys: set[str], per_minute: int, trust_proxy: bool):
        self.app, self.keys, self.per_minute, self.trust_proxy = app, keys, per_minute, trust_proxy
        self.hits: dict[str, deque] = defaultdict(deque)

    def _ip(self, scope) -> str:
        headers = dict(scope.get("headers") or [])
        if self.trust_proxy and b"x-forwarded-for" in headers:
            return headers[b"x-forwarded-for"].decode().split(",")[0].strip()
        client = scope.get("client") or ("?", 0)
        return client[0]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        size = headers.get(b"content-length")
        if size and size.isdigit() and int(size) > MAX_BODY:
            return await JSONResponse({"error": "request too large"}, 413)(scope, receive, send)
        key = headers.get(b"x-api-key", b"").decode()
        if key and key not in self.keys:
            return await JSONResponse({"error": "invalid API key"}, 401)(scope, receive, send)
        if not key and scope["path"] not in ("/agents/healthz", mail_intake.intake_path()):  # mail is signed
            now, q = time.monotonic(), self.hits[self._ip(scope)]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return await JSONResponse({"error": "too many requests; try again in a minute"}, 429,
                                          headers={"Retry-After": "60"})(scope, receive, send)
            q.append(now)
        token = agent_api.authorized.set(bool(key))
        try:
            return await self.app(scope, receive, send)
        finally:
            agent_api.authorized.reset(token)


def app(public_url: str = "", allowed_hosts: list[str] | None = None, per_minute: int | None = None) -> Gate:
    keys = _keys()
    if os.environ.get("BILLRADAR_AGENT_LIVE") == "1" and not keys:
        raise RuntimeError("BILLRADAR_AGENT_LIVE=1 needs BILLRADAR_AGENT_KEYS; refusing to start open")
    public_url = public_url or os.environ.get("BILLRADAR_PUBLIC_URL", "http://127.0.0.1:8000")
    hosts = allowed_hosts or [h.strip() for h in os.environ.get("BILLRADAR_PUBLIC_HOSTS", "").split(",") if h.strip()]
    host = public_url.split("://", 1)[-1].split("/", 1)[0]
    hosts = sorted(set(hosts + [host]))
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts,
                                         allowed_origins=[f"https://{h}" for h in hosts] + [f"http://{h}" for h in hosts])
    mcp_app = mcp_server.build_server().streamable_http_app(
        streamable_http_path="/mcp", stateless_http=True, json_response=True, max_request_body_size=MAX_BODY,
        transport_security=security, host="0.0.0.0")

    async def intake(request: Request):
        """Forwarded mail from the Cloudflare Worker: signed, for a known address, from a listed sender.
        The checks answer at once (the Worker rejects the mail on an error); reading runs after."""
        secret = os.environ.get(mail_intake.SECRET_ENV, "")
        if not secret:
            return JSONResponse({"error": "email intake is not set up"}, 503)
        raw = await request.body()
        if len(raw) > mail_intake.MAX_MESSAGE:
            return JSONResponse({"error": "too large"}, 413)
        if not mail_intake.verify_signature(raw, request.headers.get("x-billradar-timestamp", ""),
                                            request.headers.get("x-billradar-signature", ""), secret):
            return JSONResponse({"error": "bad signature"}, 401)
        token = mail_intake.token_from(request.headers.get("x-billradar-to", ""))
        index = agent_api.INTAKE_INDEX
        runs = json.loads(index.read_text()) if token and index.exists() else {}
        if token not in runs:
            return JSONResponse({"error": "unknown address"}, 404)
        run_dir = Path(runs[token])
        sender = request.headers.get("x-billradar-from", "").lower()
        if sender not in mail_intake._state(run_dir).get("senders", []):
            return JSONResponse({"error": "sender not allowed for this address"}, 403)

        def work():
            try:
                mail_intake.ingest(run_dir, raw, providers.make_client(), via="routing", envelope_from=sender)
            except Exception as exc:  # recorded for the case screen; the mail itself was accepted
                (run_dir / "intake-error.json").write_text(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return JSONResponse({"accepted": True}, 202, background=BackgroundTask(work))

    async def healthz(_):
        return JSONResponse({"ok": True, "live": agent_api.live_enabled(), "mcp": "/mcp", "a2a": "/a2a",
                             "card": "/.well-known/agent-card.json"})

    star = Starlette(routes=[Route("/agents/healthz", healthz),
                             Route(mail_intake.intake_path(), intake, methods=["POST"]),
                             *a2a_agent.routes(public_url),
                             Mount("/", app=mcp_app)],
                     lifespan=lambda _: mcp_app.router.lifespan_context(mcp_app))
    per_minute = per_minute or int(os.environ.get("BILLRADAR_AGENT_PER_MINUTE", "30"))
    return Gate(star, keys, per_minute, os.environ.get("BILLRADAR_TRUST_PROXY") == "1")
