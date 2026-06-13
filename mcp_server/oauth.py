"""Minimal OAuth 2.1 provider for the KDP MCP bridge.

Implements just enough of RFC 8414 (metadata), RFC 7591 (dynamic registration),
RFC 7636 (PKCE) and OAuth 2.1 authorization-code flow for Claude.ai's custom
connector dialog to attach a Bearer credential to our MCP server.

The user proves possession of the shared KDP_API_TOKEN on the consent screen;
the issued access token IS that same shared token. State (clients + auth codes)
is kept in memory — acceptable for a single-user personal deployment.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

_AUTH_CODE_TTL = 300  # seconds
_clients: dict[str, dict] = {}
_auth_codes: dict[str, dict] = {}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def make_endpoints(public_url: str, issuer_url: str, shared_token: str):
    """Return Starlette endpoint callables bound to the given config.

    public_url:  the externally visible base URL of the MCP service.
    issuer_url:  the OAuth `issuer` identifier (may be a sub-path of public_url
                 when the root .well-known path is intercepted by infra).
    """

    token_bytes = shared_token.encode("utf-8")

    async def authorization_server_metadata(_request: Request):
        return JSONResponse({
            "issuer": issuer_url,
            "authorization_endpoint": f"{public_url}/oauth/authorize",
            "token_endpoint": f"{public_url}/oauth/token",
            "registration_endpoint": f"{public_url}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256", "plain"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
            "scopes_supported": ["mcp"],
        })

    async def protected_resource_metadata(_request: Request):
        return JSONResponse({
            "resource": public_url,
            "authorization_servers": [issuer_url],
            "scopes_supported": ["mcp"],
            "bearer_methods_supported": ["header"],
        })

    async def register(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        client_id = secrets.token_urlsafe(16)
        client_secret = secrets.token_urlsafe(32)
        redirect_uris = body.get("redirect_uris", [])
        _clients[client_id] = {
            "client_secret": client_secret,
            "redirect_uris": redirect_uris,
        }
        return JSONResponse({
            "client_id": client_id,
            "client_secret": client_secret,
            "client_id_issued_at": int(time.time()),
            "client_secret_expires_at": 0,
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        })

    def _render_consent(params: dict, error: str = "") -> HTMLResponse:
        html = _CONSENT_HTML.format(
            client_id=params.get("client_id", ""),
            redirect_uri=params.get("redirect_uri", ""),
            state=params.get("state", ""),
            code_challenge=params.get("code_challenge", ""),
            code_challenge_method=params.get("code_challenge_method", ""),
            error=f'<p class="error">{error}</p>' if error else "",
        )
        return HTMLResponse(html, status_code=401 if error else 200)

    async def authorize(request: Request):
        if request.method == "GET":
            return _render_consent(dict(request.query_params))

        form = await request.form()
        presented = form.get("token", "").encode("utf-8")
        if not hmac.compare_digest(presented, token_bytes):
            return _render_consent(dict(form), error="Token ungültig")

        code = secrets.token_urlsafe(32)
        _auth_codes[code] = {
            "client_id": form.get("client_id", ""),
            "redirect_uri": form.get("redirect_uri", ""),
            "code_challenge": form.get("code_challenge", ""),
            "code_challenge_method": form.get("code_challenge_method", "plain"),
            "expires_at": time.time() + _AUTH_CODE_TTL,
        }
        redirect = form.get("redirect_uri", "")
        params = {"code": code}
        state = form.get("state", "")
        if state:
            params["state"] = state
        sep = "&" if "?" in redirect else "?"
        return RedirectResponse(f"{redirect}{sep}{urlencode(params)}", status_code=302)

    async def token(request: Request):
        form = await request.form()
        if form.get("grant_type") != "authorization_code":
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

        code = form.get("code", "")
        entry = _auth_codes.pop(code, None)
        if entry is None or entry["expires_at"] < time.time():
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

        challenge = entry.get("code_challenge", "")
        if challenge:
            verifier = form.get("code_verifier", "")
            method = entry.get("code_challenge_method", "plain")
            computed = (
                _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
                if method == "S256" else verifier
            )
            if not hmac.compare_digest(computed, challenge):
                return JSONResponse({"error": "invalid_grant", "detail": "pkce_mismatch"}, status_code=400)

        return JSONResponse({
            "access_token": shared_token,
            "token_type": "Bearer",
            "expires_in": 31_536_000,
            "scope": "mcp",
        })

    return {
        "authorization_server_metadata": authorization_server_metadata,
        "protected_resource_metadata": protected_resource_metadata,
        "register": register,
        "authorize": authorize,
        "token": token,
    }


_CONSENT_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claude autorisieren – KDP Platform</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 460px; margin: 80px auto; padding: 20px;
         background: #f5f5f7; color: #1d1d1f; }}
  .card {{ background: #fff; padding: 30px; border-radius: 14px;
          box-shadow: 0 4px 16px rgba(0,0,0,0.06); }}
  h1 {{ font-size: 20px; margin: 0 0 8px; }}
  p {{ color: #555; font-size: 14px; line-height: 1.45; }}
  input[type=password] {{ width: 100%; padding: 12px;
        border: 1px solid #d2d2d7; border-radius: 8px;
        font: 14px/1 ui-monospace, monospace; box-sizing: border-box; }}
  button {{ width: 100%; padding: 12px; margin-top: 12px;
           background: #1e40af; color: #fff; border: 0;
           border-radius: 8px; font-size: 15px; cursor: pointer; }}
  button:hover {{ background: #1e3a8a; }}
  .error {{ color: #c00; font-size: 13px; margin: 8px 0 0; }}
</style>
</head>
<body>
  <div class="card">
    <h1>Claude autorisieren</h1>
    <p>Claude möchte auf deine KDP-Plattform zugreifen. Bestätige mit deinem KDP-API-Token.</p>
    {error}
    <form method="POST">
      <input type="hidden" name="client_id" value="{client_id}">
      <input type="hidden" name="redirect_uri" value="{redirect_uri}">
      <input type="hidden" name="state" value="{state}">
      <input type="hidden" name="code_challenge" value="{code_challenge}">
      <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
      <input type="password" name="token" autofocus autocomplete="off" placeholder="API-Token">
      <button type="submit">Autorisieren</button>
    </form>
  </div>
</body>
</html>
"""
