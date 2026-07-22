from flask import Blueprint, request

from database import create_user, get_user, list_user_measurements, list_users
from .auth import require_role
from .responses import error_response, success_response

user_api = Blueprint("user_api", __name__)


@user_api.post("/api/users")
def create_user_resource():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error_response(
            "JSON 요청 본문이 필요합니다.",
            status=400,
            error_type="request",
        )

    user = create_user(data)

    return success_response(
        "회원가입이 완료되었습니다.",
        {"user": user},
        status=201,
    )


@user_api.get("/api/users")
@require_role("admin")
def list_user_resources():
    keyword = request.args.get("keyword", "")
    users = list_users(keyword)

    return success_response(
        "사용자 목록을 조회했습니다.",
        {
            "users": users,
            "keyword": keyword,
        },
    )


@user_api.get("/api/users/<string:user_id>")
@require_role("admin")
def get_user_resource(user_id: str):
    user = get_user(user_id)

    if user is None:
        return error_response(
            "사용자를 찾을 수 없습니다.",
            status=404,
            error_type="not_found",
        )

    return success_response(
        "사용자 정보를 조회했습니다.",
        {"user": user},
    )


@user_api.get("/api/users/<string:user_id>/measurements")
@require_role("admin")
def get_user_measurements(user_id: str):
    user = get_user(user_id)

    if user is None:
        return error_response(
            "사용자를 찾을 수 없습니다.",
            status=404,
            error_type="not_found",
        )

    return success_response(
        "사용자의 측정 정보를 조회했습니다.",
        {
            "user": user,
            "measurements": list_user_measurements(user_id),
        },
    )
