import hashlib
import hmac
import json
import math
import os
import secrets
import tempfile
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

DATE_FORMAT = "%Y-%m-%d"
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))

BACK_DIR = Path(__file__).resolve().parent
DATA_PATH = Path(
    os.getenv("HEALTH_DATA_PATH", str(BACK_DIR / "data.json"))
).resolve()
LEGACY_DB_PATH = Path(
    os.getenv(
        "HEALTH_LEGACY_DB_PATH",
        str(DATA_PATH.with_name("health_measurement.db")),
    )
).resolve()

ADMIN_ID = os.getenv("HEALTH_ADMIN_ID", "admin")
ADMIN_PASSWORD = os.getenv("HEALTH_ADMIN_PASSWORD", "admin")

STATUS_NEUTRAL = "neutral"
STATUS_YELLOW = "yellow"
STATUS_GREEN = "green"
STATUS_ORANGE = "orange"
STATUS_RED = "red"

_DATA_LOCK = threading.RLock()
_SESSION_LOCK = threading.RLock()
_SESSIONS: dict[str, dict[str, str]] = {}


class DataStoreError(RuntimeError):
    """JSON 파일 읽기 또는 저장 중 발생한 저장소 오류."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    if salt is None:
        salt = os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
    )
    return f"{salt.hex()}:{password_hash.hex()}"


def verify_password(password: str, stored_value: str) -> bool:
    try:
        salt_hex, expected_hash_hex = stored_value.split(":", 1)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, TypeError):
        return False

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
    )
    return hmac.compare_digest(actual_hash.hex(), expected_hash_hex)


def _default_store() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "users": [],
        "measurements": [],
        "next_measurement_id": 1,
    }


def _write_store_unlocked(store: dict[str, Any]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Optional[Path] = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=DATA_PATH.parent,
            prefix=f".{DATA_PATH.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            json.dump(
                store,
                temporary_file,
                ensure_ascii=False,
                indent=2,
            )
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, DATA_PATH)
    except OSError as error:
        raise DataStoreError(
            f"JSON 데이터 파일을 저장하지 못했습니다: {error}"
        ) from error
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def _read_store_unlocked() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return _default_store()

    try:
        with DATA_PATH.open("r", encoding="utf-8") as data_file:
            raw_store = json.load(data_file)
    except json.JSONDecodeError as error:
        raise DataStoreError(
            f"data.json 형식이 올바르지 않습니다: "
            f"{error.lineno}행 {error.colno}열"
        ) from error
    except OSError as error:
        raise DataStoreError(
            f"JSON 데이터 파일을 읽지 못했습니다: {error}"
        ) from error

    return _normalize_store(raw_store)


def _normalize_store(raw_store: Any) -> dict[str, Any]:
    if not isinstance(raw_store, dict):
        raise DataStoreError("data.json의 최상위 값은 객체여야 합니다.")

    users = raw_store.get("users", [])
    measurements = raw_store.get("measurements", [])

    if not isinstance(users, list):
        raise DataStoreError("data.json의 users는 배열이어야 합니다.")

    if not isinstance(measurements, list):
        raise DataStoreError(
            "data.json의 measurements는 배열이어야 합니다."
        )

    normalized_users: list[dict[str, Any]] = []

    for user in users:
        if not isinstance(user, dict):
            continue

        user_id = str(user.get("user_id", "")).strip()
        password_hash = str(user.get("pw", "")).strip()
        name = str(user.get("name", "")).strip()
        birth = str(user.get("birth", "")).strip()

        if not all([user_id, password_hash, name, birth]):
            continue

        normalized_users.append(
            {
                "user_id": user_id,
                "pw": password_hash,
                "name": name,
                "birth": birth,
            }
        )

    normalized_measurements: list[dict[str, Any]] = []
    largest_id = 0

    for measurement in measurements:
        if not isinstance(measurement, dict):
            continue

        try:
            measurement_id = int(measurement["id"])
            user_id = str(measurement["user_id"]).strip()
            measurement_date = parse_date(
                str(measurement["date"]),
                "측정 날짜",
            ).isoformat()
            height = float(measurement["height"])
            weight = float(measurement["weight"])
            systolic = int(measurement["systolic"])
            diastolic = int(measurement["diastolic"])
            blood_sugar = float(measurement["blood_sugar"])
        except (KeyError, TypeError, ValueError):
            continue

        assessment = calculate_health_assessment(
            height,
            weight,
            systolic,
            diastolic,
            blood_sugar,
        )

        memo_value = measurement.get("memo")
        memo = (
            str(memo_value).strip() or None
            if memo_value is not None
            else None
        )

        normalized_measurements.append(
            {
                "id": measurement_id,
                "user_id": user_id,
                "date": measurement_date,
                "height": height,
                "weight": weight,
                "systolic": systolic,
                "diastolic": diastolic,
                "blood_sugar": blood_sugar,
                **_assessment_for_storage(assessment),
                "memo": memo,
            }
        )

        largest_id = max(largest_id, measurement_id)

    try:
        requested_next_id = int(
            raw_store.get("next_measurement_id", largest_id + 1)
        )
    except (TypeError, ValueError):
        requested_next_id = largest_id + 1

    return {
        "schema_version": 1,
        "users": normalized_users,
        "measurements": normalized_measurements,
        "next_measurement_id": max(
            largest_id + 1,
            requested_next_id,
            1,
        ),
    }


def _load_store() -> dict[str, Any]:
    with _DATA_LOCK:
        return _read_store_unlocked()


def _migrate_legacy_sqlite_unlocked() -> Optional[dict[str, Any]]:
    if not LEGACY_DB_PATH.exists():
        return None

    try:
        import sqlite3

        connection = sqlite3.connect(LEGACY_DB_PATH)
        connection.row_factory = sqlite3.Row

        table_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

        if "users" not in table_names or "measurements" not in table_names:
            connection.close()
            return None

        users = [
            dict(row)
            for row in connection.execute(
                "SELECT user_id, pw, name, birth FROM users"
            ).fetchall()
        ]

        raw_measurements = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    date,
                    height,
                    weight,
                    systolic,
                    diastolic,
                    blood_sugar,
                    memo
                FROM measurements
                ORDER BY id
                """
            ).fetchall()
        ]

        connection.close()
    except Exception as error:
        raise DataStoreError(
            f"기존 SQLite 데이터를 JSON으로 변환하지 못했습니다: {error}"
        ) from error

    measurements: list[dict[str, Any]] = []
    largest_id = 0

    for row in raw_measurements:
        assessment = calculate_health_assessment(
            row.get("height"),
            row.get("weight"),
            row.get("systolic"),
            row.get("diastolic"),
            row.get("blood_sugar"),
        )

        measurement_id = int(row["id"])
        largest_id = max(largest_id, measurement_id)

        measurements.append(
            {
                "id": measurement_id,
                "user_id": row["user_id"],
                "date": row["date"],
                "height": float(row["height"]),
                "weight": float(row["weight"]),
                "systolic": int(row["systolic"]),
                "diastolic": int(row["diastolic"]),
                "blood_sugar": float(row["blood_sugar"]),
                **_assessment_for_storage(assessment),
                "memo": row.get("memo"),
            }
        )

    return _normalize_store(
        {
            "schema_version": 1,
            "users": users,
            "measurements": measurements,
            "next_measurement_id": largest_id + 1,
        }
    )


def initialize_database() -> None:
    """기존 함수명을 유지하지만 실제 저장소는 JSON 파일이다."""
    with _DATA_LOCK:
        if not DATA_PATH.exists():
            migrated_store = _migrate_legacy_sqlite_unlocked()
            store = migrated_store or _default_store()
            _write_store_unlocked(store)
            return

        normalized_store = _read_store_unlocked()
        _write_store_unlocked(normalized_store)


def parse_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name}은 YYYY-MM-DD 형식의 문자열이어야 합니다."
        )

    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError(
            f"{field_name}은 YYYY-MM-DD 형식이어야 합니다."
        ) from exc


def require_text(data: dict[str, Any], key: str, label: str) -> str:
    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}을(를) 입력해 주세요.")

    return value.strip()


def require_number(
    data: dict[str, Any],
    key: str,
    label: str,
    *,
    integer: bool = False,
    minimum: float = 0,
) -> float | int:
    value = data.get(key)

    if isinstance(value, bool):
        raise ValueError(f"{label}은(는) 숫자여야 합니다.")

    try:
        number = int(value) if integer else float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}은(는) 숫자여야 합니다.") from exc

    if number < minimum:
        raise ValueError(f"{label}은(는) {minimum} 이상이어야 합니다.")

    return number


def classify_bmi(bmi: Optional[float]) -> tuple[str, str]:
    if bmi is None:
        return "해당 없음", STATUS_NEUTRAL
    if bmi < 18.5:
        return "저체중", STATUS_YELLOW
    if bmi < 23:
        return "정상", STATUS_GREEN
    if bmi < 25:
        return "과체중", STATUS_ORANGE
    return "비만", STATUS_RED


def classify_blood_pressure(
    systolic: Optional[int],
    diastolic: Optional[int],
) -> tuple[str, str]:
    if systolic is None or diastolic is None:
        return "해당 없음", STATUS_NEUTRAL

    if systolic >= 140 or diastolic >= 90:
        return "고혈압", STATUS_RED

    if systolic >= 120 or diastolic >= 80:
        return "주의", STATUS_ORANGE

    return "정상", STATUS_GREEN


def classify_fasting_glucose(
    blood_sugar: Optional[float],
) -> tuple[str, str]:
    if blood_sugar is None:
        return "해당 없음", STATUS_NEUTRAL
    if blood_sugar < 100:
        return "정상", STATUS_GREEN
    if blood_sugar <= 125:
        return "공복혈당장애", STATUS_ORANGE
    return "당뇨 의심", STATUS_RED


def calculate_health_assessment(
    height: Optional[float],
    weight: Optional[float],
    systolic: Optional[int],
    diastolic: Optional[int],
    blood_sugar: Optional[float],
) -> dict[str, Any]:
    bmi: Optional[float] = None

    if (
        height is not None
        and weight is not None
        and float(height) > 0
        and float(weight) > 0
    ):
        height_meters = float(height) / 100
        bmi = round(float(weight) / (height_meters ** 2), 1)

    bmi_category, bmi_status = classify_bmi(bmi)
    pressure_category, pressure_status = classify_blood_pressure(
        int(systolic) if systolic is not None else None,
        int(diastolic) if diastolic is not None else None,
    )
    glucose_category, glucose_status = classify_fasting_glucose(
        float(blood_sugar) if blood_sugar is not None else None
    )

    statuses = [
        bmi_status,
        pressure_status,
        glucose_status,
    ]

    if STATUS_RED in statuses:
        overall_category = "위험"
        overall_status = STATUS_RED
    elif STATUS_ORANGE in statuses:
        overall_category = "주의"
        overall_status = STATUS_ORANGE
    elif STATUS_YELLOW in statuses:
        overall_category = "관찰"
        overall_status = STATUS_YELLOW
    elif statuses and all(status == STATUS_GREEN for status in statuses):
        overall_category = "정상"
        overall_status = STATUS_GREEN
    else:
        overall_category = "해당 없음"
        overall_status = STATUS_NEUTRAL

    warnings: list[str] = []

    if bmi_status == STATUS_RED:
        warnings.append("BMI가 비만 범위입니다.")
    if pressure_status == STATUS_RED:
        warnings.append("혈압이 고혈압 범위입니다.")
    if glucose_status == STATUS_RED:
        warnings.append("공복 혈당이 당뇨 의심 범위입니다.")

    return {
        "bmi": bmi,
        "bmi_category": bmi_category,
        "bmi_status": bmi_status,
        "blood_pressure_category": pressure_category,
        "blood_pressure_status": pressure_status,
        "fasting_glucose_category": glucose_category,
        "fasting_glucose_status": glucose_status,
        "overall_category": overall_category,
        "overall_status": overall_status,
        "warning_message": "\n".join(warnings) if warnings else None,
        "warnings": warnings,
    }


def _assessment_for_storage(
    assessment: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in assessment.items()
        if key != "warnings"
    }


def _serialize_measurement(
    measurement: dict[str, Any],
) -> dict[str, Any]:
    result = dict(measurement)
    warning_message = result.get("warning_message")

    result["warnings"] = (
        [
            line.strip()
            for line in str(warning_message).splitlines()
            if line.strip()
        ]
        if warning_message
        else []
    )

    return result


def create_user(data: dict[str, Any]) -> dict[str, str]:
    user_id = require_text(data, "user_id", "사용자 ID")
    password = require_text(data, "pw", "비밀번호")
    name = require_text(data, "name", "이름")
    birth = parse_date(
        require_text(data, "birth", "생년월일"),
        "생년월일",
    )

    if len(password) < 4:
        raise ValueError("비밀번호는 4자 이상이어야 합니다.")

    if birth > date.today():
        raise ValueError("생년월일은 미래 날짜일 수 없습니다.")

    with _DATA_LOCK:
        store = _read_store_unlocked()

        if any(
            user["user_id"] == user_id
            for user in store["users"]
        ):
            raise ValueError("이미 존재하는 사용자 ID입니다.")

        store["users"].append(
            {
                "user_id": user_id,
                "pw": hash_password(password),
                "name": name,
                "birth": birth.isoformat(),
            }
        )

        _write_store_unlocked(store)

    return {
        "user_id": user_id,
        "name": name,
        "birth": birth.isoformat(),
    }


def authenticate_user(user_id: str, password: str) -> bool:
    store = _load_store()

    user = next(
        (
            item
            for item in store["users"]
            if item["user_id"] == user_id
        ),
        None,
    )

    return (
        user is not None
        and verify_password(password, user["pw"])
    )


def authenticate_admin(admin_id: str, password: str) -> bool:
    return (
        hmac.compare_digest(admin_id, ADMIN_ID)
        and hmac.compare_digest(password, ADMIN_PASSWORD)
    )


def create_session(role: str, account_id: str) -> dict[str, str]:
    if role not in {"user", "admin"}:
        raise ValueError("올바르지 않은 역할입니다.")

    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(hours=SESSION_HOURS)

    session = {
        "token": token,
        "role": role,
        "account_id": account_id,
        "expires_at": expires_at.isoformat(),
    }

    with _SESSION_LOCK:
        _remove_expired_sessions_unlocked()
        _SESSIONS[token] = session

    return dict(session)


def _remove_expired_sessions_unlocked() -> None:
    current_time = utc_now()

    expired_tokens = []

    for token, session in _SESSIONS.items():
        try:
            expires_at = datetime.fromisoformat(
                session["expires_at"]
            )
        except (KeyError, ValueError):
            expired_tokens.append(token)
            continue

        if expires_at <= current_time:
            expired_tokens.append(token)

    for token in expired_tokens:
        _SESSIONS.pop(token, None)


def get_session(token: str) -> Optional[dict[str, str]]:
    with _SESSION_LOCK:
        _remove_expired_sessions_unlocked()
        session = _SESSIONS.get(token)

        return dict(session) if session is not None else None


def delete_session(token: str) -> None:
    with _SESSION_LOCK:
        _SESSIONS.pop(token, None)


def _parse_measurement_payload(
    data: dict[str, Any],
) -> dict[str, Any]:
    measurement_date = parse_date(
        require_text(data, "date", "측정 날짜"),
        "측정 날짜",
    )

    if measurement_date > date.today():
        raise ValueError("미래 날짜의 측정 정보는 입력할 수 없습니다.")

    height = require_number(
        data,
        "height",
        "키",
        minimum=0.1,
    )
    weight = require_number(
        data,
        "weight",
        "몸무게",
        minimum=0.1,
    )
    systolic = require_number(
        data,
        "systolic",
        "수축기 혈압",
        integer=True,
        minimum=1,
    )
    diastolic = require_number(
        data,
        "diastolic",
        "이완기 혈압",
        integer=True,
        minimum=1,
    )
    blood_sugar = require_number(
        data,
        "blood_sugar",
        "공복 혈당",
        minimum=0,
    )

    if systolic <= diastolic:
        raise ValueError(
            "수축기 혈압은 이완기 혈압보다 커야 합니다."
        )

    memo_value = data.get("memo")

    if memo_value is not None and not isinstance(memo_value, str):
        raise ValueError("메모는 문자열이어야 합니다.")

    return {
        "date": measurement_date.isoformat(),
        "height": float(height),
        "weight": float(weight),
        "systolic": int(systolic),
        "diastolic": int(diastolic),
        "blood_sugar": float(blood_sugar),
        "memo": (
            memo_value.strip() or None
            if isinstance(memo_value, str)
            else None
        ),
    }


def _user_measurements(
    store: dict[str, Any],
    user_id: str,
    *,
    exclude_measurement_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    return [
        measurement
        for measurement in store["measurements"]
        if measurement["user_id"] == user_id
        and (
            exclude_measurement_id is None
            or measurement["id"] != exclude_measurement_id
        )
    ]


def _validate_measurement_consistency(
    existing_measurements: list[dict[str, Any]],
    candidate: dict[str, Any],
) -> None:
    candidate_date = parse_date(
        candidate["date"],
        "측정 날짜",
    )

    if any(
        measurement["date"] == candidate["date"]
        for measurement in existing_measurements
    ):
        raise ValueError(
            "해당 날짜의 다른 측정 정보가 이미 존재합니다."
        )

    date_labels = {
        (candidate_date - timedelta(days=1)).isoformat(): "전날",
        (candidate_date + timedelta(days=1)).isoformat(): "다음 날",
    }

    for measurement in existing_measurements:
        label = date_labels.get(measurement["date"])

        if label is None:
            continue

        height_difference = abs(
            candidate["height"] - float(measurement["height"])
        )
        weight_difference = abs(
            candidate["weight"] - float(measurement["weight"])
        )

        if height_difference >= 3:
            raise ValueError(
                f"{label} 키와 {height_difference:.1f}cm 차이가 납니다. "
                "인접 날짜 대비 3cm 이상 차이 나는 값은 "
                "입력할 수 없습니다."
            )

        if weight_difference >= 5:
            raise ValueError(
                f"{label} 몸무게와 {weight_difference:.1f}kg "
                "차이가 납니다. 인접 날짜 대비 5kg 이상 "
                "차이 나는 값은 입력할 수 없습니다."
            )


def create_measurement(
    user_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    payload = _parse_measurement_payload(data)

    with _DATA_LOCK:
        store = _read_store_unlocked()

        if not any(
            user["user_id"] == user_id
            for user in store["users"]
        ):
            raise ValueError("사용자를 찾을 수 없습니다.")

        existing = _user_measurements(store, user_id)
        _validate_measurement_consistency(existing, payload)

        assessment = calculate_health_assessment(
            payload["height"],
            payload["weight"],
            payload["systolic"],
            payload["diastolic"],
            payload["blood_sugar"],
        )

        measurement_id = int(store["next_measurement_id"])

        measurement = {
            "id": measurement_id,
            "user_id": user_id,
            **payload,
            **_assessment_for_storage(assessment),
        }

        store["measurements"].append(measurement)
        store["next_measurement_id"] = measurement_id + 1
        _write_store_unlocked(store)

    return _serialize_measurement(measurement)


def update_measurement(
    measurement_id: int,
    user_id: str,
    data: dict[str, Any],
) -> Optional[dict[str, Any]]:
    payload = _parse_measurement_payload(data)

    with _DATA_LOCK:
        store = _read_store_unlocked()

        measurement_index = next(
            (
                index
                for index, measurement in enumerate(
                    store["measurements"]
                )
                if measurement["id"] == measurement_id
                and measurement["user_id"] == user_id
            ),
            None,
        )

        if measurement_index is None:
            return None

        existing = _user_measurements(
            store,
            user_id,
            exclude_measurement_id=measurement_id,
        )
        _validate_measurement_consistency(existing, payload)

        assessment = calculate_health_assessment(
            payload["height"],
            payload["weight"],
            payload["systolic"],
            payload["diastolic"],
            payload["blood_sugar"],
        )

        updated = {
            "id": measurement_id,
            "user_id": user_id,
            **payload,
            **_assessment_for_storage(assessment),
        }

        store["measurements"][measurement_index] = updated
        _write_store_unlocked(store)

    return _serialize_measurement(updated)


def _normalize_optional_date(
    value: Optional[str],
    field_name: str,
) -> Optional[str]:
    if value is None:
        return None

    normalized = value.strip()

    if not normalized:
        return None

    return parse_date(normalized, field_name).isoformat()


def _normalize_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    normalized_start = _normalize_optional_date(
        start_date,
        "조회 시작일",
    )
    normalized_end = _normalize_optional_date(
        end_date,
        "조회 종료일",
    )

    if (
        normalized_start is not None
        and normalized_end is not None
        and normalized_start > normalized_end
    ):
        raise ValueError(
            "조회 시작일은 종료일보다 늦을 수 없습니다."
        )

    return normalized_start, normalized_end


def _normalize_pagination(
    page: Any,
    page_size: Any,
) -> tuple[int, int]:
    try:
        normalized_page = int(page)
        normalized_page_size = int(page_size)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "페이지 번호와 페이지 크기는 정수여야 합니다."
        ) from exc

    if normalized_page < 1:
        raise ValueError("페이지 번호는 1 이상이어야 합니다.")

    if normalized_page_size < 1 or normalized_page_size > 50:
        raise ValueError(
            "페이지 크기는 1 이상 50 이하여야 합니다."
        )

    return normalized_page, normalized_page_size


def _filtered_measurements(
    store: dict[str, Any],
    user_id: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> list[dict[str, Any]]:
    result = []

    for measurement in store["measurements"]:
        if measurement["user_id"] != user_id:
            continue
        if start_date is not None and measurement["date"] < start_date:
            continue
        if end_date is not None and measurement["date"] > end_date:
            continue

        result.append(measurement)

    result.sort(
        key=lambda item: (item["date"], int(item["id"])),
        reverse=True,
    )
    return result


def search_user_measurements(
    user_id: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 5,
) -> dict[str, Any]:
    normalized_start, normalized_end = _normalize_date_range(
        start_date,
        end_date,
    )
    normalized_page, normalized_page_size = _normalize_pagination(
        page,
        page_size,
    )

    store = _load_store()
    filtered = _filtered_measurements(
        store,
        user_id,
        normalized_start,
        normalized_end,
    )

    total_count = len(filtered)
    total_pages = (
        math.ceil(total_count / normalized_page_size)
        if total_count > 0
        else 0
    )

    effective_page = normalized_page

    if total_pages > 0 and effective_page > total_pages:
        effective_page = total_pages

    offset = (effective_page - 1) * normalized_page_size
    page_items = filtered[
        offset:offset + normalized_page_size
    ]

    return {
        "measurements": [
            _serialize_measurement(measurement)
            for measurement in page_items
        ],
        "pagination": {
            "page": effective_page,
            "page_size": normalized_page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_previous": effective_page > 1,
            "has_next": (
                total_pages > 0
                and effective_page < total_pages
            ),
        },
        "filters": {
            "start_date": normalized_start,
            "end_date": normalized_end,
        },
    }


def list_user_measurements(
    user_id: str,
) -> list[dict[str, Any]]:
    store = _load_store()

    return [
        _serialize_measurement(measurement)
        for measurement in _filtered_measurements(
            store,
            user_id,
            None,
            None,
        )
    ]


def _average(
    measurements: list[dict[str, Any]],
    field_name: str,
) -> Optional[float]:
    values = [
        float(measurement[field_name])
        for measurement in measurements
        if measurement.get(field_name) is not None
    ]

    if not values:
        return None

    return round(sum(values) / len(values), 1)


def get_measurement_statistics(
    user_id: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    normalized_start, normalized_end = _normalize_date_range(
        start_date,
        end_date,
    )

    store = _load_store()
    measurements = _filtered_measurements(
        store,
        user_id,
        normalized_start,
        normalized_end,
    )

    averages = {
        "height": _average(measurements, "height"),
        "weight": _average(measurements, "weight"),
        "bmi": _average(measurements, "bmi"),
        "systolic": _average(measurements, "systolic"),
        "diastolic": _average(measurements, "diastolic"),
        "blood_sugar": _average(
            measurements,
            "blood_sugar",
        ),
    }

    bmi_category, bmi_status = classify_bmi(
        averages["bmi"]
    )
    pressure_category, pressure_status = (
        classify_blood_pressure(
            round(averages["systolic"])
            if averages["systolic"] is not None
            else None,
            round(averages["diastolic"])
            if averages["diastolic"] is not None
            else None,
        )
    )
    glucose_category, glucose_status = (
        classify_fasting_glucose(
            averages["blood_sugar"]
        )
    )

    dates = [
        measurement["date"]
        for measurement in measurements
    ]

    return {
        "measurement_count": len(measurements),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "filters": {
            "start_date": normalized_start,
            "end_date": normalized_end,
        },
        "averages": averages,
        "classifications": {
            "bmi": {
                "category": bmi_category,
                "status": bmi_status,
            },
            "blood_pressure": {
                "category": pressure_category,
                "status": pressure_status,
            },
            "fasting_glucose": {
                "category": glucose_category,
                "status": glucose_status,
            },
        },
    }


def get_measurement(
    measurement_id: int,
) -> Optional[dict[str, Any]]:
    store = _load_store()

    measurement = next(
        (
            item
            for item in store["measurements"]
            if int(item["id"]) == int(measurement_id)
        ),
        None,
    )

    return (
        _serialize_measurement(measurement)
        if measurement is not None
        else None
    )


def delete_measurement(measurement_id: int) -> bool:
    with _DATA_LOCK:
        store = _read_store_unlocked()

        original_count = len(store["measurements"])
        store["measurements"] = [
            measurement
            for measurement in store["measurements"]
            if int(measurement["id"]) != int(measurement_id)
        ]

        deleted = len(store["measurements"]) != original_count

        if deleted:
            _write_store_unlocked(store)

        return deleted


def list_users(keyword: str = "") -> list[dict[str, Any]]:
    normalized_keyword = keyword.strip().lower()
    store = _load_store()

    users = []

    for user in store["users"]:
        if normalized_keyword and (
            normalized_keyword not in user["user_id"].lower()
            and normalized_keyword not in user["name"].lower()
        ):
            continue

        measurements = [
            measurement
            for measurement in store["measurements"]
            if measurement["user_id"] == user["user_id"]
        ]

        users.append(
            {
                "user_id": user["user_id"],
                "name": user["name"],
                "birth": user["birth"],
                "measurement_count": len(measurements),
                "risk_count": sum(
                    1
                    for measurement in measurements
                    if measurement.get("overall_status")
                    == STATUS_RED
                ),
            }
        )

    users.sort(key=lambda item: item["user_id"])
    return users


def get_user(user_id: str) -> Optional[dict[str, Any]]:
    store = _load_store()

    user = next(
        (
            item
            for item in store["users"]
            if item["user_id"] == user_id
        ),
        None,
    )

    if user is None:
        return None

    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "birth": user["birth"],
    }
