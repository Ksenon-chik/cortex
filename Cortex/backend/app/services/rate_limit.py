from collections import defaultdict, deque
from collections.abc import Hashable
from time import monotonic

from fastapi import HTTPException, Request, status


_WINDOWS: dict[Hashable, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def enforce_rate_limit(
    request: Request,
    scope: str,
    limit: int,
    window_seconds: int,
    actor: str | None = None,
) -> None:
    now = monotonic()
    key = (scope, actor or _client_ip(request))
    window = _WINDOWS[key]
    while window and now - window[0] > window_seconds:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
    window.append(now)
