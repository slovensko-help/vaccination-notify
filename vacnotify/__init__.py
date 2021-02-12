import json
import locale
import sentry_sdk
import subprocess

from flask_assets import Environment
from flask_wtf.csrf import CSRFError
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from flask import Flask, render_template, request
from celery import Celery, Task
from flask_cors import CORS
from flask_migrate import Migrate
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_mail import Mail
from webassets import Bundle

from vacnotify.utils import CustomEncoder, remove_pii


app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile("config.py", silent=True)
app.json_encoder = CustomEncoder


def before_send(event, hint):
    if "request" in event and "data" in event["request"] and "email" in event["request"]["data"]:
        event["request"]["data"]["email"] = remove_pii(event["request"]["data"]["email"])
    if "location" in event and event["location"] in ("vacnotify.tasts.email_confirmation",
                                                     "vacnotify.tasts.email_notification_spot",
                                                     "vacnotify.tasts.email_notification_group"):
        celery_args = event["extra"]["celery-job"]["args"]
        celery_args[0] = remove_pii(celery_args[0])
    return event


sentry_sdk.init(
    dsn=app.config["SENTRY_INGEST"],
    integrations=[FlaskIntegration(), SqlalchemyIntegration(), CeleryIntegration()],
    traces_sample_rate=app.config["SENTRY_SAMPLE_RATE"],
    environment=app.env,
    debug=app.debug,
    before_send=before_send
)

try:
    locale.setlocale(locale.LC_ALL, "sk_SK.UTF-8")
except locale.Error:
    pass

try:
    with app.open_instance_resource("alerts.json") as f:
        alerts = json.load(f)
except FileNotFoundError:
    alerts = []

with app.open_instance_resource("claims.json") as f:
    vapid_claims = json.load(f)
with app.open_instance_resource("vapid_privkey.der") as f:
    vapid_privkey = f.read().decode()
with app.open_instance_resource("vapid_pubkey.der") as f:
    vapid_pubkey = f.read().decode()

try:
    res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if res:
        release = res.stdout.decode().strip()
    else:
        release = "vacnotify"
except:
    pass

# webassets
assets = Environment(app)
js_libs = Bundle("lib/polyfill.min.js", "lib/jquery.min.js", "lib/bootstrap.bundle.min.js",
                 "lib/d3.min.js", "lib/d3-legend.min.js",
                 "lib/sentry.min.js", "lib/sentry.tracing.min.js", output="gen/libs.js")
js_mine = Bundle("polyfill.js", "mail.js", "base.js", filters="rjsmin", output="gen/mine.js")
css_libs = Bundle("lib/bootstrap.min.css", "lib/fontawesome.min.css", output="gen/libs.css")
css_mine = Bundle("base.css", output="gen/mine.css")
assets.register("js_libs", js_libs)
assets.register("js_mine", js_mine)
assets.register("css_libs", css_libs)
assets.register("css_mine", css_mine)


# DB
db = SQLAlchemy(app)


# Celery
def make_celery(app):
    class ContextTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL'],
        result_backend=app.config['CELERY_RESULT_BACKEND'],
        task_cls=ContextTask,
        timezone="Europe/Bratislava"
    )
    return celery


celery = make_celery(app)

# Redis
rds = FlaskRedis(app)

# CSRF protection
csrf = CSRFProtect(app)

# CORS (Cross-Origin Resource Sharing)
cors = CORS(app, origins="")

# Migrate
migrate = Migrate(app, db, directory="vacnotify/migrations")

# Email
mail = Mail(app)

from .tasks.query import run
from .tasks.maintenance import clear_db_unconfirmed


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(app.config["QUERY_PERIOD"], run.s(), name="Query the state.")
    sender.add_periodic_task(24 * 3600, clear_db_unconfirmed.s(), name="Clear unconfirmed and old subscriptions.")


from .views import main
app.register_blueprint(main)

from .commands import *


@app.before_request
def set_sentry_user():
    try:
        sentry_sdk.set_user({"ip_address": request.remote_addr})
    except Exception:
        pass


@app.errorhandler(404)
def errorhandler_notfound(error):
    return render_template("error.html.jinja2", error="Stránka neexistuje."), 404


@app.errorhandler(CSRFError)
def errorhandler_csrf(error):
    return render_template("error.html.jinja2", error="Nepodarilo sa overiť CSRF token. Skúste prosím použiť iný webový prehliadač alebo okno inkognito."), 400


@app.errorhandler(403)
def errorhandler_hcaptcha(error):
    return render_template("error.html.jinja2", error="Prístup zamietnutý."), 403


@app.errorhandler(Exception)
def errorhandler_exc(error: Exception):
    sentry_sdk.capture_exception(error)
    return render_template("error.html.jinja2", error="Chyba servera, pravdepodobne som niečo pokazil. Skúste znova."), 500


@app.template_global()
def get_alerts():
    return alerts


@app.template_global()
def get_release():
    return release


@app.template_global()
def format_timedelta(ts):
    def format_inner(s):
        if s < 60:
            return [f"{s} sekúnd" if s != 1 else f"{s} sekunda"]
        if s < 3600:
            m = int(s // 60)
            res = [f"{m} minút" if m != 1 else f"{m} minúta"]
            if s % 60 != 0:
                res.extend(format_inner(s % 60))
            return res
        if s < 86400:
            h = int(s // 3600)
            res = [f"{h} hodín" if h != 1 else f"{h} hodina"]
            if s % 3600 != 0:
                res.extend(format_inner(s % 3600))
            return res
        d = int(s // 86400)
        res = [f"{d} dní" if d != 1 else f"{d} deň"]
        if s % 86400 != 0:
            res.extend(format_inner(s % 86400))
        return res

    vlist = format_inner(ts)
    if len(vlist) == 1:
        return vlist[0]
    else:
        return ", ".join(vlist[:-1]) + " a " + vlist[-1]
