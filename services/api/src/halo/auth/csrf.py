import secrets

from halo.errors import HaloError

CSRF_COOKIE = "halo_csrf"
CSRF_HEADER = "x-csrf-token"


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def assert_csrf(cookie_token: str | None, header_token: str | None) -> None:
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HaloError(403, "CSRF_FAILED", "CSRF token missing or mismatched.")
