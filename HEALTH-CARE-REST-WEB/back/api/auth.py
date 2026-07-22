from functools import wraps
from typing import Optional

from flask import g, request

from database import get_session
from .responses import error_response


def extract_bearer_token() -> Optional[str]:
    authorization = request.headers.get("Authorization", "").strip()

    if not authorization:
        return None

    scheme, separator, token = authorization.partition(" ")

    if not separator or scheme.lower() != "bearer" or not token.strip():
        return None

    return token.strip()


def require_role(required_role: Optional[str] = None):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            token = extract_bearer_token()

            if token is None:
                return error_response(
                    "로그인이 필요합니다.",
                    status=401,
                    error_type="authentication",
                )

            session = get_session(token)

            if session is None:
                return error_response(
                    "세션이 만료되었거나 유효하지 않습니다.",
                    status=401,
                    error_type="authentication",
                )

            if required_role is not None and session["role"] != required_role:
                return error_response(
                    "해당 기능에 접근할 권한이 없습니다.",
                    status=403,
                    error_type="permission",
                )

            g.session = session
            g.token = token
            return view(*args, **kwargs)

        return wrapped_view

    return decorator
