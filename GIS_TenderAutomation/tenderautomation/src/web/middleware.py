from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if "text/html" in response.headers.get("content-type", ""):
            response.headers.update({
                "Content-Security-Policy": (
                    "default-src 'self'; "
                    "style-src 'self' cdn.jsdelivr.net; "
                    "script-src 'self' cdn.jsdelivr.net"
                ),
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            })
        return response
