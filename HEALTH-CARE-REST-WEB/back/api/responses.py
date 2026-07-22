from typing import Any, Optional

from flask import jsonify


def success_response(
    message: str,
    data: Optional[Any] = None,
    status: int = 200,
):
    payload: dict[str, Any] = {
        "success": True,
        "message": message,
    }

    if data is not None:
        payload["data"] = data

    return jsonify(payload), status


def error_response(
    message: str,
    status: int = 400,
    error_type: str = "validation",
):
    return jsonify(
        {
            "success": False,
            "message": message,
            "error_type": error_type,
        }
    ), status
