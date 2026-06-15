"""DETAS dashboard route'lari."""

from flask import Blueprint, render_template


dashboard_blueprint = Blueprint("dashboard", __name__)


@dashboard_blueprint.route("/", endpoint="index")
def index():
    return render_template("index.html")
