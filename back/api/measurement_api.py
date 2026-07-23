from flask import Blueprint, g, request

from database import (
    create_measurement,
    delete_measurement,
    get_measurement,
    list_user_measurements,
)
from .auth import require_role
from .responses import error_response, success_response

measurement_api = Blueprint("measurement_api", __name__)


@measurement_api.get("/api/measurements")
@require_role("user")
def list_measurement_resources():
    measurements = list_user_measurements(
        g.session["account_id"]
    )

    return success_response(
        "본인의 측정 정보를 조회했습니다.",
        {"measurements": measurements},
    )


@measurement_api.post("/api/measurements")
@require_role("user")
def create_measurement_resource():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error_response(
            "JSON 요청 본문이 필요합니다.",
            status=400,
            error_type="request",
        )

    measurement = create_measurement(
        g.session["account_id"],
        data,
    )

    return success_response(
        "건강 수치 계산 후 측정 정보가 저장되었습니다.",
        {
            "measurement": measurement,
            "warnings": measurement.get("warnings", []),
        },
        status=201,
    )


@measurement_api.get("/api/measurements/<int:measurement_id>")
@require_role()
def get_measurement_resource(measurement_id: int):
    measurement = get_measurement(measurement_id)

    if measurement is None:
        return error_response(
            "측정 정보를 찾을 수 없습니다.",
            status=404,
            error_type="not_found",
        )

    if (
        g.session["role"] == "user"
        and measurement["user_id"] != g.session["account_id"]
    ):
        return error_response(
            "다른 사용자의 측정 정보는 조회할 수 없습니다.",
            status=403,
            error_type="permission",
        )

    return success_response(
        "측정 정보를 조회했습니다.",
        {"measurement": measurement},
    )


@measurement_api.delete("/api/measurements/<int:measurement_id>")
@require_role()
def delete_measurement_resource(measurement_id: int):
    measurement = get_measurement(measurement_id)

    if measurement is None:
        return error_response(
            "삭제할 측정 정보를 찾을 수 없습니다.",
            status=404,
            error_type="not_found",
        )

    role = g.session["role"]
    account_id = g.session["account_id"]

    if role == "user" and measurement["user_id"] != account_id:
        return error_response(
            "다른 사용자의 측정 정보는 삭제할 수 없습니다.",
            status=403,
            error_type="permission",
        )

    if not delete_measurement(measurement_id):
        return error_response(
            "측정 정보 삭제에 실패했습니다.",
            status=409,
            error_type="delete_failed",
        )

    return success_response(
        "측정 기록이 삭제되었습니다.",
        {
            "measurement_id": measurement_id,
            "user_id": measurement["user_id"],
            "deleted_by": {
                "role": role,
                "account_id": account_id,
            },
        },
    )
