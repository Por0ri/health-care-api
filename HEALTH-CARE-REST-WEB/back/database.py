import hashlib
import hmac
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
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       TEXT NOT NULL,
                date          TEXT NOT NULL,
                height        REAL NOT NULL CHECK (height > 0),
                weight        REAL NOT NULL CHECK (weight > 0),
                systolic      INTEGER NOT NULL CHECK (systolic > 0),
                diastolic     INTEGER NOT NULL CHECK (diastolic > 0),
                blood_sugar   REAL NOT NULL CHECK (blood_sugar >= 0),
                memo          TEXT DEFAULT NULL,

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
        "혈당",
        minimum=0,
    )

    if systolic <= diastolic:
        raise ValueError("수축기 혈압은 이완기 혈압보다 커야 합니다.")

    memo_value = data.get("memo")
    if memo_value is not None and not isinstance(memo_value, str):
        raise ValueError("메모는 문자열이어야 합니다.")

    memo = memo_value.strip() or None if isinstance(memo_value, str) else None
    previous_date = (measurement_date - timedelta(days=1)).isoformat()

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
                memo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                measurement_date.isoformat(),
                height,
                weight,
                systolic,
                diastolic,
                blood_sugar,
                memo,
            ),
        )

        measurement_id = int(cursor.lastrowid)

    measurement = get_measurement(measurement_id)
    if measurement is None:
        raise RuntimeError("저장된 측정 정보를 조회하지 못했습니다.")

    return measurement


def list_user_measurements(user_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
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
            WHERE user_id = ?
            ORDER BY date DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_measurement(measurement_id: int) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM measurements WHERE id = ?",
            (measurement_id,),
        ).fetchone()

    return dict(row) if row is not None else None


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
                COUNT(m.id) AS measurement_count
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
