"""MCP bridge exposing the MBA T-Shirt Factory backend as a remote MCP server.

Speaks MCP-over-Streamable-HTTP so Claude Code (web + desktop) and the Claude.ai
consumer apps can connect from anywhere. Authentication is twofold:

  * Inbound MCP traffic carries a Bearer access token that we validate against
    the shared MBA_API_TOKEN.
  * For Claude.ai's Custom Connector dialog (which only offers OAuth), we
    expose a minimal OAuth 2.1 provider in oauth.py. The user proves they own
    the shared token on a consent screen, and the access token we issue IS
    that same shared token.
"""

import hmac
import logging
import os
from urllib.parse import urlparse

import httpx
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from oauth import make_endpoints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mba-mcp")

MBA_API_URL = os.environ.get("MBA_API_URL", "http://backend:8000").rstrip("/")
MBA_API_TOKEN = os.environ.get("MBA_API_TOKEN", "")
MCP_PORT = int(os.environ.get("MCP_PORT", "9000"))
MCP_PUBLIC_URL = os.environ.get("MCP_PUBLIC_URL", "https://mcp.mba.ooopppmmm.com").rstrip("/")
# OAuth issuer is a sub-path so the well-known metadata sits at
# /oauth/.well-known/... — outside the root .well-known/* that Coolify/Traefik
# intercepts for ACME.
OAUTH_ISSUER = f"{MCP_PUBLIC_URL}/oauth"

if not MBA_API_TOKEN:
    raise RuntimeError(
        "MBA_API_TOKEN environment variable is required for the MCP bridge."
    )

# FastMCP enforces DNS-rebinding protection by validating the inbound Host
# header. By default only localhost is accepted, so we must explicitly allow
# our public hostname or every authenticated /mcp call gets a 421.
_public_host = urlparse(MCP_PUBLIC_URL).netloc

mcp = FastMCP(
    "mba-tshirt",
    transport_security=TransportSecuritySettings(
        allowed_hosts=[
            _public_host,
            "127.0.0.1",
            "localhost",
            "127.0.0.1:9000",
            "localhost:9000",
        ],
        allowed_origins=[
            "https://claude.ai",
            "https://*.claude.ai",
            "https://anthropic.com",
        ],
    ),
)

_client = httpx.AsyncClient(
    base_url=MBA_API_URL,
    headers={"Authorization": f"Bearer {MBA_API_TOKEN}"},
    timeout=30.0,
)


async def _get(path: str, params: dict | None = None) -> dict | list:
    try:
        r = await _client.get(path, params=params)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"backend returned {e.response.status_code}", "body": e.response.text[:500]}
    except httpx.HTTPError as e:
        return {"error": "backend unreachable", "detail": str(e)}


# ─── T-Shirt Factory tools ───────────────────────────────────────────

@mcp.tool()
async def tsf_health() -> dict:
    """Check whether the MBA backend is healthy and reachable."""
    return await _get("/api/health")


@mcp.tool()
async def tsf_dashboard() -> dict:
    """Full T-Shirt Factory dashboard: slot usage, performance, learning, seasonal upcoming, top niches."""
    return await _get("/api/v1/tsf/dashboard")


@mcp.tool()
async def tsf_list_designs(status: str | None = None, limit: int = 50) -> list:
    """List generated design prompts. Optional status filter."""
    params: dict = {"limit": min(limit, 200)}
    if status:
        params["status"] = status
    return await _get("/api/v1/tsf/designs", params=params)


@mcp.tool()
async def tsf_list_niches() -> list:
    """Niche profiles ordered by win-rate."""
    return await _get("/api/v1/tsf/niches")


@mcp.tool()
async def tsf_slot_summary() -> dict:
    """Current MBA slot usage and availability."""
    return await _get("/api/v1/tsf/slots/summary")


@mcp.tool()
async def tsf_performance_summary() -> dict:
    """Overall performance summary across uploaded designs."""
    return await _get("/api/v1/tsf/performance/summary")


@mcp.tool()
async def tsf_learning_insights(category: str | None = None, min_confidence: float = 0.0) -> list:
    """Persistent self-learning insights from past design performance."""
    params: dict = {"min_confidence": min_confidence}
    if category:
        params["category"] = category
    return await _get("/api/v1/tsf/learning/insights", params=params)


# ─── Inbound bearer auth ─────────────────────────────────────────────

def _is_public(path: str) -> bool:
    return (
        path == "/healthz"
        or path.startswith("/oauth/")
        or path.startswith("/.well-known/")
        or path in ("/register", "/authorize", "/token")
    )


class RequestLogger(BaseHTTPMiddleware):
    """Logs every inbound request, even those that 401 — vital for debugging
    why a remote MCP client (Claude.ai) is unhappy."""

    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path
        ua = request.headers.get("user-agent", "-")
        has_auth = "yes" if request.headers.get("authorization") else "no"
        logger.info(f"-> {method} {path} ua={ua!r} auth={has_auth}")
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception(f"!! {method} {path}: {exc}")
            raise
        logger.info(f"<- {response.status_code} {method} {path}")
        return response


class BearerAuth(BaseHTTPMiddleware):
    def __init__(self, app, token: str, resource_metadata_url: str):
        super().__init__(app)
        self._token_bytes = token.encode("utf-8")
        self._challenge = (
            f'Bearer realm="mcp", resource_metadata="{resource_metadata_url}"'
        )

    async def dispatch(self, request: Request, call_next):
        if _is_public(request.url.path):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(
                {"error": "missing_bearer"}, status_code=401,
                headers={"WWW-Authenticate": self._challenge},
            )
        presented = auth.removeprefix("Bearer ").strip().encode("utf-8")
        if not hmac.compare_digest(presented, self._token_bytes):
            return JSONResponse(
                {"error": "invalid_token"}, status_code=401,
                headers={"WWW-Authenticate": self._challenge + ', error="invalid_token"'},
            )
        return await call_next(request)


async def _healthz(_request):
    return JSONResponse({"status": "ok"})


def build_app():
    app = mcp.streamable_http_app()

    resource_metadata_url = f"{MCP_PUBLIC_URL}/oauth/.well-known/oauth-protected-resource"

    app.add_middleware(BearerAuth, token=MBA_API_TOKEN,
                       resource_metadata_url=resource_metadata_url)
    app.add_middleware(RequestLogger)

    ep = make_endpoints(MCP_PUBLIC_URL, OAUTH_ISSUER, MBA_API_TOKEN)

    auth_server_metadata_paths = (
        "/oauth/.well-known/oauth-authorization-server",
        "/.well-known/oauth-authorization-server/oauth",
        "/.well-known/oauth-authorization-server",
        "/oauth/.well-known/openid-configuration",
        "/.well-known/openid-configuration/oauth",
        "/.well-known/openid-configuration",
    )
    resource_metadata_paths = (
        "/oauth/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource",
    )

    for p in auth_server_metadata_paths:
        app.router.routes.append(
            Route(p, ep["authorization_server_metadata"], methods=["GET"])
        )
    for p in resource_metadata_paths:
        app.router.routes.append(
            Route(p, ep["protected_resource_metadata"], methods=["GET"])
        )

    app.router.routes.extend([
        Route("/healthz", _healthz, methods=["GET"]),
        Route("/oauth/register", ep["register"], methods=["POST"]),
        Route("/oauth/authorize", ep["authorize"], methods=["GET", "POST"]),
        Route("/oauth/token", ep["token"], methods=["POST"]),
        Route("/register", ep["register"], methods=["POST"]),
        Route("/authorize", ep["authorize"], methods=["GET", "POST"]),
        Route("/token", ep["token"], methods=["POST"]),
    ])
    return app


if __name__ == "__main__":
    logger.info(f"MBA MCP bridge starting on :{MCP_PORT}, backend={MBA_API_URL}")
    uvicorn.run(build_app(), host="0.0.0.0", port=MCP_PORT)
