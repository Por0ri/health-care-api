from .measurement_api import measurement_api
from .session_api import session_api
from .system_api import system_api
from .user_api import user_api


def register_blueprints(app) -> None:
    app.register_blueprint(system_api)
    app.register_blueprint(user_api)
    app.register_blueprint(session_api)
    app.register_blueprint(measurement_api)
