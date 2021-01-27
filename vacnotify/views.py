from flask import render_template

from vacnotify.blueprint import main
from vacnotify.models import VaccinationPlace


@main.route("/")
def index():
    return render_template("index.html.jinja2")
