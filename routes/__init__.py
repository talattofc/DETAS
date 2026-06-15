"""DETAS Flask Blueprint kayitlari."""

from flask import current_app


def get_route_service(name):
    """app.extensions icinden route servis fonksiyonunu dondurur."""
    services = current_app.extensions.get("detas_services", {})
    return services.get(name)


def register_routes(app):
    """Tum DETAS Blueprint'lerini Flask uygulamasina kaydeder."""
    from routes.api_routes import api_blueprint
    from routes.dashboard_routes import dashboard_blueprint
    from routes.video_routes import video_blueprint

    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(api_blueprint)
    app.register_blueprint(video_blueprint)
