from flask import Flask
from celery import Celery, Task
from flask_cors import CORS
from flask_migrate import Migrate
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect


app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile("config.py", silent=True)


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
        task_cls=ContextTask
    )
    celery.conf.update(app.config)
    return celery


celery = make_celery(app)

# Redis
rds = FlaskRedis(app)

# CSRF protection
csrf = CSRFProtect(app)

# CORS (Cross-Origin Resource Sharing)
cors = CORS(app, origins="")

# DB
db = SQLAlchemy(app)

# Migrate
migrate = Migrate(app, db, directory="vacnotify/migrations")


from .views import main
app.register_blueprint(main)

