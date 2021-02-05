import json
import locale
import sentry_sdk

from sentry_sdk.integrations.flask import FlaskIntegration
from flask import Flask, render_template, session
from celery import Celery, Task
from flask_cors import CORS
from flask_migrate import Migrate
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_mail import Mail
from vacnotify.utils import CustomEncoder, remove_pii


app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile("config.py", silent=True)
app.json_encoder = CustomEncoder


def before_send(event, hint):
    if "request" in event and "data" in event["request"] and "email" in event["request"]["data"]:
        event["request"]["data"]["email"] = remove_pii(event["request"]["data"]["email"])
    if "location" in event and event["location"] in ("vacnotify.tasts.email_confirmation", "vacnotify.tasts.email_notification_spot", "vacnotify.tasts.email_notification_group"):
        celery_args = event["extra"]["celery-job"]["args"]
        celery_args[0] = remove_pii(celery_args[0])
    return event


sentry_sdk.init(
    dsn=app.config["SENTRY_INGEST"],
    integrations=[FlaskIntegration()],
    traces_sample_rate=app.config["SENTRY_SAMPLE_RATE"],
    environment=app.env,
    debug=app.debug,
    before_send=before_send
)

try:
    locale.setlocale(locale.LC_ALL, "sk_SK.UTF-8")
except locale.Error:
    pass

with app.open_resource("useragents.json") as f:
    useragents = json.load(f)

try:
    with app.open_instance_resource("alerts.json") as f:
        alerts = json.load(f)
except FileNotFoundError:
    alerts = []
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
        user = []
        for k, v in session.items():
            user.append(str(k))
            user.append(str(v))
        user_hash = remove_pii(*user)[:10]
        sentry_sdk.set_user({"id": user_hash})
    except Exception:
        pass


@app.errorhandler(404)
def errorhandler_notfound(error):
    return render_template("error.html.jinja2", error="Stránka neexistuje."), 404


@app.errorhandler(403)
def errorhandler_hcaptcha(error):
    return render_template("error.html.jinja2", error="Prístup zamietnutý."), 403


@app.errorhandler(Exception)
def errorhandler_exc(error: Exception):
    sentry_sdk.capture_exception(error)
    app.logger.error(str(error))
    return render_template("error.html.jinja2", error="Chyba servera, pravdepodobne som niečo pokazil. Skúste znova."), 500


@app.template_global()
def get_alerts():
    return alerts
