import os
import sqlite3

from flask import Flask
from werkzeug.exceptions import HTTPException

from api import register_blueprints
from api.responses import error_response
from database import DB_PATH, initialize_database

HOST = os.getenv("HEALTH_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("HEALTH_SERVER_PORT", "5000"))


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False

    initialize_database()
    register_blueprints(app)

    @app.after_request
    def add_api_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValueError)
    def handle_value_error(error: ValueError):
        return error_response(
            str(error),
            status=400,
            error_type="validation",
        )

    @app.errorhandler(sqlite3.IntegrityError)
    def handle_integrity_error(error: sqlite3.IntegrityError):
        return error_response(
            "데이터 제약조건을 확인해 주세요.",
            status=409,
            error_type="database_constraint",
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        return error_response(
            error.description,
            status=error.code or 500,
            error_type="http",
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        app.logger.exception("처리되지 않은 서버 오류")
        return error_response(
            "서버 처리 중 오류가 발생했습니다.",
            status=500,
            error_type="server",
        )

    return app


app = create_app()


if __name__ == "__main__":
    print("=" * 58)
    print("Health Care REST API 서버가 실행됩니다.")
    print(f"주소: http://{HOST}:{PORT}")
    print(f"API 목록: http://127.0.0.1:{PORT}/api")
    print(f"SQLite DB: {DB_PATH}")
    print("기본 관리자: admin / admin")
    print("=" * 58)

    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
