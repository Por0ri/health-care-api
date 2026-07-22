from flask import Blueprint, g, request

from database import (
    authenticate_admin,
    authenticate_user,
    create_session,
    delete_session,
    require_text,
)
from .auth import require_role
from .responses import error_response, success_response

session_api = Blueprint("session_api", __name__)


@session_api.post("/api/sessions")
def create_session_resource():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error_response(
            "JSON 요청 본문이 필요합니다.",
            status=400,
            error_type="request",
        )

    role = require_text(data, "role", "역할")
    account_id = require_text(data, "account_id", "계정 ID")
    password = require_text(data, "pw", "비밀번호")

    if role == "user":
        authenticated = authenticate_user(account_id, password)
    elif role == "admin":
        authenticated = authenticate_admin(account_id, password)
    else:
        return error_response(
            "역할은 user 또는 admin이어야 합니다.",
            status=400,
            error_type="validation",
        )

    if not authenticated:
        return error_response(
            "ID 또는 비밀번호가 올바르지 않습니다.",
            status=401,
            error_type="authentication",
        )

    session = create_session(role, account_id)

    return success_response(
        "로그인되었습니다.",
        {"session": session},
        status=201,
    )


@session_api.delete("/api/sessions/current")
@require_role()
def delete_current_session():
    delete_session(g.token)
    return success_response("로그아웃되었습니다.")
