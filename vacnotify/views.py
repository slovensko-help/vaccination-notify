from flask import render_template
from flask_mail import Message
from vacnotify.blueprint import main
from vacnotify.models import *
from vacnotify import mail


@main.route("/")
def index():
    return render_template("index.html.jinja2")
