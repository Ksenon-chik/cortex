import secrets

from fastapi import Cookie, Header, HTTPException, status


CSRF_COOKIE_NAME = "cortex_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


async def validate_csrf(
    csrf_cookie: str | None = Cookie(None, alias=CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(None, alias=CSRF_HEADER_NAME),
) -> None:
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )
