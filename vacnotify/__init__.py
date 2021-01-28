import json

from flask import Flask, render_template
from celery import Celery, Task
from flask_cors import CORS
from flask_migrate import Migrate
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_mail import Mail

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile("config.py", silent=True)

with app.open_resource("useragents.json") as f:
    useragents = json.load(f)

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

from .tasks import run


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(app.config["QUERY_PERIOD"], run.s(), name="Query the state!")


from .views import main
app.register_blueprint(main)


@app.errorhandler(404)
def errorhandler(error):
    return render_template("error.html.jinja2", error="Stránka neexistuje.")


@app.errorhandler(Exception)
def errorhandler_exc(error):
    return render_template("error.html.jinja2", error="Chyba servera, pravdepodobne som niečo pokazil. Skúste znova.")

