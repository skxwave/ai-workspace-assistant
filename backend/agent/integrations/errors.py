import httpx

AUTH_STATUS_CODES = frozenset({401, 403})

_MAX_CAUSE_DEPTH = 10


def is_auth_failure(error: BaseException | None, depth: int = 0) -> bool:
    """True if `error` was ultimately caused by rejected credentials."""
    if error is None or depth > _MAX_CAUSE_DEPTH:
        return False
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in AUTH_STATUS_CODES
    if isinstance(error, BaseExceptionGroup):
        return any(is_auth_failure(exc, depth + 1) for exc in error.exceptions)
    return is_auth_failure(error.__cause__ or error.__context__, depth + 1)
