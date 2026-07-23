import hashlib
import hmac
import math
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

DATE_FORMAT = "%Y-%m-%d"
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))
BACK_DIR = Path(__file__).resolve().parent
DB_PATH = Path(
    os.getenv("HEALTH_DB_PATH", str(BACK_DIR / "health_measurement.db"))
).resolve()

STATUS_NEUTRAL = "neutral"
STATUS_YELLOW = "yellow"
STATUS_GREEN = "green"
STATUS_ORANGE = "orange"
STATUS_RED = "red"

DERIVED_MEASUREMENT_COLUMNS = {
    "bmi": "REAL",
    "bmi_category": "TEXT NOT NULL DEFAULT '해당 없음'",
    "bmi_status": "TEXT NOT NULL DEFAULT 'neutral'",
    "blood_pressure_category": "TEXT NOT NULL DEFAULT '해당 없음'",
    "blood_pressure_status": "TEXT NOT NULL DEFAULT 'neutral'",
    "fasting_glucose_category": "TEXT NOT NULL DEFAULT '해당 없음'",
    "fasting_glucose_status": "TEXT NOT NULL DEFAULT 'neutral'",
    "overall_category": "TEXT NOT NULL DEFAULT '해당 없음'",
    "overall_status": "TEXT NOT NULL DEFAULT 'neutral'",
    "warning_message": "TEXT DEFAULT NULL",
}


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


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


def _ensure_measurement_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(measurements)").fetchall()
    }

    for column_name, column_definition in DERIVED_MEASUREMENT_COLUMNS.items():
        if column_name in existing_columns:
            continue

        try:
            conn.execute(
                f"ALTER TABLE measurements "
                f"ADD COLUMN {column_name} {column_definition}"
            )
        except sqlite3.OperationalError as error:
            # Gunicorn 워커가 동시에 초기화할 때 다른 워커가 먼저
            # 컬럼을 추가했다면 중복 컬럼 오류만 무시한다.
            if "duplicate column name" not in str(error).lower():
                raise


def _status_priority(status: str) -> int:
    priorities = {
        STATUS_NEUTRAL: 0,
        STATUS_GREEN: 1,
        STATUS_YELLOW: 2,
        STATUS_ORANGE: 3,
        STATUS_RED: 4,
    }
    return priorities.get(status, 0)


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

    if systolic < 120 and diastolic < 80:
        return "정상", STATUS_GREEN

    return "해당 없음", STATUS_NEUTRAL


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
    blood_pressure_category, blood_pressure_status = classify_blood_pressure(
        int(systolic) if systolic is not None else None,
        int(diastolic) if diastolic is not None else None,
    )
    fasting_glucose_category, fasting_glucose_status = (
        classify_fasting_glucose(
            float(blood_sugar) if blood_sugar is not None else None
        )
    )

    statuses = [
        bmi_status,
        blood_pressure_status,
        fasting_glucose_status,
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
    if blood_pressure_status == STATUS_RED:
        warnings.append("혈압이 고혈압 범위입니다.")
    if fasting_glucose_status == STATUS_RED:
        warnings.append("공복 혈당이 당뇨 의심 범위입니다.")

    warning_message = "\n".join(warnings) if warnings else None

    return {
        "bmi": bmi,
        "bmi_category": bmi_category,
        "bmi_status": bmi_status,
        "blood_pressure_category": blood_pressure_category,
        "blood_pressure_status": blood_pressure_status,
        "fasting_glucose_category": fasting_glucose_category,
        "fasting_glucose_status": fasting_glucose_status,
        "overall_category": overall_category,
        "overall_status": overall_status,
        "warning_message": warning_message,
        "warnings": warnings,
    }


def _serialize_measurement(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    measurement = dict(row)
    warning_message = measurement.get("warning_message")

    measurement["warnings"] = (
        [
            line.strip()
            for line in str(warning_message).splitlines()
            if line.strip()
        ]
        if warning_message
        else []
    )

    return measurement


def _recalculate_existing_measurements(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT
            id,
            height,
            weight,
            systolic,
            diastolic,
            blood_sugar
        FROM measurements
        """
    ).fetchall()

    for row in rows:
        assessment = calculate_health_assessment(
            row["height"],
            row["weight"],
            row["systolic"],
            row["diastolic"],
            row["blood_sugar"],
        )

        conn.execute(
            """
            UPDATE measurements
            SET
                bmi = ?,
                bmi_category = ?,
                bmi_status = ?,
                blood_pressure_category = ?,
                blood_pressure_status = ?,
                fasting_glucose_category = ?,
                fasting_glucose_status = ?,
                overall_category = ?,
                overall_status = ?,
                warning_message = ?
            WHERE id = ?
            """,
            (
                assessment["bmi"],
                assessment["bmi_category"],
                assessment["bmi_status"],
                assessment["blood_pressure_category"],
                assessment["blood_pressure_status"],
                assessment["fasting_glucose_category"],
                assessment["fasting_glucose_status"],
                assessment["overall_category"],
                assessment["overall_status"],
                assessment["warning_message"],
                row["id"],
            ),
        )


def initialize_database() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                pw      TEXT NOT NULL,
                name    TEXT NOT NULL,
                birth   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admins (
                admin_id TEXT PRIMARY KEY,
                pw       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS measurements (
                id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id                    TEXT NOT NULL,
                date                       TEXT NOT NULL,
                height                     REAL NOT NULL CHECK (height > 0),
                weight                     REAL NOT NULL CHECK (weight > 0),
                systolic                   INTEGER NOT NULL CHECK (systolic > 0),
                diastolic                  INTEGER NOT NULL CHECK (diastolic > 0),
                blood_sugar                REAL NOT NULL CHECK (blood_sugar >= 0),
                bmi                        REAL,
                bmi_category               TEXT NOT NULL DEFAULT '해당 없음',
                bmi_status                 TEXT NOT NULL DEFAULT 'neutral',
                blood_pressure_category    TEXT NOT NULL DEFAULT '해당 없음',
                blood_pressure_status      TEXT NOT NULL DEFAULT 'neutral',
                fasting_glucose_category   TEXT NOT NULL DEFAULT '해당 없음',
                fasting_glucose_status     TEXT NOT NULL DEFAULT 'neutral',
                overall_category           TEXT NOT NULL DEFAULT '해당 없음',
                overall_status             TEXT NOT NULL DEFAULT 'neutral',
                warning_message            TEXT DEFAULT NULL,
                memo                       TEXT DEFAULT NULL,

                FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
                    ON UPDATE CASCADE
                    ON DELETE CASCADE,

                UNIQUE (user_id, date)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token       TEXT PRIMARY KEY,
                role        TEXT NOT NULL CHECK (role IN ('user', 'admin')),
                account_id  TEXT NOT NULL,
                expires_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_measurements_user_date
                ON measurements(user_id, date);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
                ON sessions(expires_at);
            """
        )

        _ensure_measurement_columns(conn)

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_measurements_overall_status
            ON measurements(overall_status)
            """
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO admins (admin_id, pw)
            VALUES (?, ?)
            """,
            ("admin", hash_password("admin")),
        )

        conn.execute(
            "DELETE FROM sessions WHERE expires_at <= ?",
            (utc_now().isoformat(),),
        )

        _recalculate_existing_measurements(conn)


def parse_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}은 YYYY-MM-DD 형식의 문자열이어야 합니다.")

    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError(f"{field_name}은 YYYY-MM-DD 형식이어야 합니다.") from exc


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


def create_user(data: dict[str, Any]) -> dict[str, str]:
    user_id = require_text(data, "user_id", "사용자 ID")
    password = require_text(data, "pw", "비밀번호")
    name = require_text(data, "name", "이름")
    birth = parse_date(require_text(data, "birth", "생년월일"), "생년월일")

    if len(password) < 4:
        raise ValueError("비밀번호는 4자 이상이어야 합니다.")

    if birth > date.today():
        raise ValueError("생년월일은 미래 날짜일 수 없습니다.")

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if exists:
            raise ValueError("이미 존재하는 사용자 ID입니다.")

        conn.execute(
            """
            INSERT INTO users (user_id, pw, name, birth)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, hash_password(password), name, birth.isoformat()),
        )

    return {
        "user_id": user_id,
        "name": name,
        "birth": birth.isoformat(),
    }


def authenticate_user(user_id: str, password: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT pw FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    return row is not None and verify_password(password, row["pw"])


def authenticate_admin(admin_id: str, password: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT pw FROM admins WHERE admin_id = ?",
            (admin_id,),
        ).fetchone()

    return row is not None and verify_password(password, row["pw"])


def create_session(role: str, account_id: str) -> dict[str, str]:
    if role not in {"user", "admin"}:
        raise ValueError("올바르지 않은 역할입니다.")

    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(hours=SESSION_HOURS)

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE expires_at <= ?",
            (utc_now().isoformat(),),
        )
        conn.execute(
            """
            INSERT INTO sessions (token, role, account_id, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, role, account_id, expires_at.isoformat()),
        )

    return {
        "token": token,
        "role": role,
        "account_id": account_id,
        "expires_at": expires_at.isoformat(),
    }


def get_session(token: str) -> Optional[dict[str, str]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT token, role, account_id, expires_at
            FROM sessions
            WHERE token = ?
            """,
            (token,),
        ).fetchone()

        if row is None:
            return None

        session = dict(row)

        try:
            expires_at = datetime.fromisoformat(session["expires_at"])
        except ValueError:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None

        if expires_at <= utc_now():
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None

    return session


def delete_session(token: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def create_measurement(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    measurement_date = parse_date(
        require_text(data, "date", "측정 날짜"),
        "측정 날짜",
    )

    if measurement_date > date.today():
        raise ValueError("미래 날짜의 측정 정보는 입력할 수 없습니다.")

    height = require_number(data, "height", "키", minimum=0.1)
    weight = require_number(data, "weight", "몸무게", minimum=0.1)
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
        raise ValueError("수축기 혈압은 이완기 혈압보다 커야 합니다.")

    memo_value = data.get("memo")
    if memo_value is not None and not isinstance(memo_value, str):
        raise ValueError("메모는 문자열이어야 합니다.")

    memo = memo_value.strip() or None if isinstance(memo_value, str) else None
    previous_date = (measurement_date - timedelta(days=1)).isoformat()

    assessment = calculate_health_assessment(
        float(height),
        float(weight),
        int(systolic),
        int(diastolic),
        float(blood_sugar),
    )

    with get_connection() as conn:
        duplicate = conn.execute(
            """
            SELECT 1
            FROM measurements
            WHERE user_id = ? AND date = ?
            """,
            (user_id, measurement_date.isoformat()),
        ).fetchone()

        if duplicate:
            raise ValueError("해당 날짜의 측정 정보가 이미 존재합니다.")

        previous = conn.execute(
            """
            SELECT height, weight
            FROM measurements
            WHERE user_id = ? AND date = ?
            """,
            (user_id, previous_date),
        ).fetchone()

        if previous is not None:
            height_difference = abs(float(height) - previous["height"])
            weight_difference = abs(float(weight) - previous["weight"])

            if height_difference >= 3:
                raise ValueError(
                    f"전날 키와 {height_difference:.1f}cm 차이가 납니다. "
                    "전날 대비 3cm 이상 차이 나는 값은 입력할 수 없습니다."
                )

            if weight_difference >= 5:
                raise ValueError(
                    f"전날 몸무게와 {weight_difference:.1f}kg 차이가 납니다. "
                    "전날 대비 5kg 이상 차이 나는 값은 입력할 수 없습니다."
                )

        cursor = conn.execute(
            """
            INSERT INTO measurements (
                user_id,
                date,
                height,
                weight,
                systolic,
                diastolic,
                blood_sugar,
                bmi,
                bmi_category,
                bmi_status,
                blood_pressure_category,
                blood_pressure_status,
                fasting_glucose_category,
                fasting_glucose_status,
                overall_category,
                overall_status,
                warning_message,
                memo
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                user_id,
                measurement_date.isoformat(),
                height,
                weight,
                systolic,
                diastolic,
                blood_sugar,
                assessment["bmi"],
                assessment["bmi_category"],
                assessment["bmi_status"],
                assessment["blood_pressure_category"],
                assessment["blood_pressure_status"],
                assessment["fasting_glucose_category"],
                assessment["fasting_glucose_status"],
                assessment["overall_category"],
                assessment["overall_status"],
                assessment["warning_message"],
                memo,
            ),
        )

        measurement_id = int(cursor.lastrowid)

    measurement = get_measurement(measurement_id)
    if measurement is None:
        raise RuntimeError("저장된 측정 정보를 조회하지 못했습니다.")

    return measurement



def update_measurement(
    measurement_id: int,
    user_id: str,
    data: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Replace one user's measurement with a complete PUT representation."""
    measurement_date = parse_date(
        require_text(data, "date", "측정 날짜"),
        "측정 날짜",
    )

    if measurement_date > date.today():
        raise ValueError("미래 날짜의 측정 정보는 입력할 수 없습니다.")

    height = require_number(data, "height", "키", minimum=0.1)
    weight = require_number(data, "weight", "몸무게", minimum=0.1)
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
        raise ValueError("수축기 혈압은 이완기 혈압보다 커야 합니다.")

    memo_value = data.get("memo")
    if memo_value is not None and not isinstance(memo_value, str):
        raise ValueError("메모는 문자열이어야 합니다.")

    memo = memo_value.strip() or None if isinstance(memo_value, str) else None
    previous_date = (measurement_date - timedelta(days=1)).isoformat()
    next_date = (measurement_date + timedelta(days=1)).isoformat()

    assessment = calculate_health_assessment(
        float(height),
        float(weight),
        int(systolic),
        int(diastolic),
        float(blood_sugar),
    )

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM measurements
            WHERE id = ? AND user_id = ?
            """,
            (measurement_id, user_id),
        ).fetchone()

        if existing is None:
            return None

        duplicate = conn.execute(
            """
            SELECT 1
            FROM measurements
            WHERE user_id = ?
              AND date = ?
              AND id <> ?
            """,
            (
                user_id,
                measurement_date.isoformat(),
                measurement_id,
            ),
        ).fetchone()

        if duplicate:
            raise ValueError("해당 날짜의 다른 측정 정보가 이미 존재합니다.")

        previous = conn.execute(
            """
            SELECT height, weight
            FROM measurements
            WHERE user_id = ?
              AND date = ?
              AND id <> ?
            """,
            (user_id, previous_date, measurement_id),
        ).fetchone()

        if previous is not None:
            height_difference = abs(float(height) - previous["height"])
            weight_difference = abs(float(weight) - previous["weight"])

            if height_difference >= 3:
                raise ValueError(
                    f"전날 키와 {height_difference:.1f}cm 차이가 납니다. "
                    "전날 대비 3cm 이상 차이 나는 값으로 수정할 수 없습니다."
                )

            if weight_difference >= 5:
                raise ValueError(
                    f"전날 몸무게와 {weight_difference:.1f}kg 차이가 납니다. "
                    "전날 대비 5kg 이상 차이 나는 값으로 수정할 수 없습니다."
                )

        following = conn.execute(
            """
            SELECT height, weight
            FROM measurements
            WHERE user_id = ?
              AND date = ?
              AND id <> ?
            """,
            (user_id, next_date, measurement_id),
        ).fetchone()

        if following is not None:
            height_difference = abs(following["height"] - float(height))
            weight_difference = abs(following["weight"] - float(weight))

            if height_difference >= 3:
                raise ValueError(
                    f"다음 날 키와 {height_difference:.1f}cm 차이가 납니다. "
                    "다음 날 기록과 3cm 이상 차이 나는 값으로 수정할 수 없습니다."
                )

            if weight_difference >= 5:
                raise ValueError(
                    f"다음 날 몸무게와 {weight_difference:.1f}kg 차이가 납니다. "
                    "다음 날 기록과 5kg 이상 차이 나는 값으로 수정할 수 없습니다."
                )

        cursor = conn.execute(
            """
            UPDATE measurements
            SET
                date = ?,
                height = ?,
                weight = ?,
                systolic = ?,
                diastolic = ?,
                blood_sugar = ?,
                bmi = ?,
                bmi_category = ?,
                bmi_status = ?,
                blood_pressure_category = ?,
                blood_pressure_status = ?,
                fasting_glucose_category = ?,
                fasting_glucose_status = ?,
                overall_category = ?,
                overall_status = ?,
                warning_message = ?,
                memo = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                measurement_date.isoformat(),
                height,
                weight,
                systolic,
                diastolic,
                blood_sugar,
                assessment["bmi"],
                assessment["bmi_category"],
                assessment["bmi_status"],
                assessment["blood_pressure_category"],
                assessment["blood_pressure_status"],
                assessment["fasting_glucose_category"],
                assessment["fasting_glucose_status"],
                assessment["overall_category"],
                assessment["overall_status"],
                assessment["warning_message"],
                memo,
                measurement_id,
                user_id,
            ),
        )

        if cursor.rowcount != 1:
            return None

    return get_measurement(measurement_id)

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
        raise ValueError("조회 시작일은 종료일보다 늦을 수 없습니다.")

    return normalized_start, normalized_end


def _normalize_pagination(
    page: Any,
    page_size: Any,
) -> tuple[int, int]:
    try:
        normalized_page = int(page)
        normalized_page_size = int(page_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("페이지 번호와 페이지 크기는 정수여야 합니다.") from exc

    if normalized_page < 1:
        raise ValueError("페이지 번호는 1 이상이어야 합니다.")

    if normalized_page_size < 1 or normalized_page_size > 50:
        raise ValueError("페이지 크기는 1 이상 50 이하여야 합니다.")

    return normalized_page, normalized_page_size


def _measurement_filter_sql(
    user_id: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[str, list[Any]]:
    conditions = ["user_id = ?"]
    parameters: list[Any] = [user_id]

    if start_date is not None:
        conditions.append("date >= ?")
        parameters.append(start_date)

    if end_date is not None:
        conditions.append("date <= ?")
        parameters.append(end_date)

    return " AND ".join(conditions), parameters


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
    where_sql, parameters = _measurement_filter_sql(
        user_id,
        normalized_start,
        normalized_end,
    )

    with get_connection() as conn:
        count_row = conn.execute(
            f"""
            SELECT COUNT(*) AS total_count
            FROM measurements
            WHERE {where_sql}
            """,
            parameters,
        ).fetchone()

        total_count = int(count_row["total_count"])
        total_pages = (
            math.ceil(total_count / normalized_page_size)
            if total_count > 0
            else 0
        )

        # 필터 결과가 줄어든 뒤 존재하지 않는 페이지를 요청하면
        # 마지막 페이지로 보정한다.
        effective_page = normalized_page
        if total_pages > 0 and effective_page > total_pages:
            effective_page = total_pages

        offset = (effective_page - 1) * normalized_page_size

        rows = conn.execute(
            f"""
            SELECT *
            FROM measurements
            WHERE {where_sql}
            ORDER BY date DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [
                *parameters,
                normalized_page_size,
                offset,
            ],
        ).fetchall()

    return {
        "measurements": [
            _serialize_measurement(row)
            for row in rows
        ],
        "pagination": {
            "page": effective_page,
            "page_size": normalized_page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_previous": effective_page > 1,
            "has_next": total_pages > 0 and effective_page < total_pages,
        },
        "filters": {
            "start_date": normalized_start,
            "end_date": normalized_end,
        },
    }


def list_user_measurements(user_id: str) -> list[dict[str, Any]]:
    """이전 내부 호출과의 호환을 위한 전체 목록 조회 함수."""
    result = search_user_measurements(
        user_id,
        page=1,
        page_size=50,
    )
    measurements = list(result["measurements"])
    total_pages = int(result["pagination"]["total_pages"])

    for page_number in range(2, total_pages + 1):
        page_result = search_user_measurements(
            user_id,
            page=page_number,
            page_size=50,
        )
        measurements.extend(page_result["measurements"])

    return measurements


def _rounded_average(value: Any) -> Optional[float]:
    if value is None:
        return None

    return round(float(value), 1)


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
    where_sql, parameters = _measurement_filter_sql(
        user_id,
        normalized_start,
        normalized_end,
    )

    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS measurement_count,
                MIN(date) AS first_date,
                MAX(date) AS last_date,
                AVG(height) AS average_height,
                AVG(weight) AS average_weight,
                AVG(bmi) AS average_bmi,
                AVG(systolic) AS average_systolic,
                AVG(diastolic) AS average_diastolic,
                AVG(blood_sugar) AS average_blood_sugar
            FROM measurements
            WHERE {where_sql}
            """,
            parameters,
        ).fetchone()

    measurement_count = int(row["measurement_count"])

    averages = {
        "height": _rounded_average(row["average_height"]),
        "weight": _rounded_average(row["average_weight"]),
        "bmi": _rounded_average(row["average_bmi"]),
        "systolic": _rounded_average(row["average_systolic"]),
        "diastolic": _rounded_average(row["average_diastolic"]),
        "blood_sugar": _rounded_average(row["average_blood_sugar"]),
    }

    bmi_category, bmi_status = classify_bmi(averages["bmi"])
    pressure_category, pressure_status = classify_blood_pressure(
        round(averages["systolic"])
        if averages["systolic"] is not None
        else None,
        round(averages["diastolic"])
        if averages["diastolic"] is not None
        else None,
    )
    glucose_category, glucose_status = classify_fasting_glucose(
        averages["blood_sugar"]
    )

    return {
        "measurement_count": measurement_count,
        "first_date": row["first_date"],
        "last_date": row["last_date"],
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



def get_measurement(measurement_id: int) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM measurements WHERE id = ?",
            (measurement_id,),
        ).fetchone()

    return _serialize_measurement(row) if row is not None else None


def delete_measurement(measurement_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM measurements WHERE id = ?",
            (measurement_id,),
        )

    return cursor.rowcount == 1


def list_users(keyword: str = "") -> list[dict[str, Any]]:
    keyword = keyword.strip()

    where_clause = ""
    params: tuple[Any, ...] = ()

    if keyword:
        where_clause = "WHERE u.user_id LIKE ? OR u.name LIKE ?"
        params = (f"%{keyword}%", f"%{keyword}%")

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                u.user_id,
                u.name,
                u.birth,
                COUNT(m.id) AS measurement_count,
                SUM(
                    CASE
                        WHEN m.overall_status = 'red' THEN 1
                        ELSE 0
                    END
                ) AS risk_count
            FROM users AS u
            LEFT JOIN measurements AS m
                ON u.user_id = m.user_id
            {where_clause}
            GROUP BY u.user_id, u.name, u.birth
            ORDER BY u.user_id
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def get_user(user_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT user_id, name, birth
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    return dict(row) if row is not None else None
