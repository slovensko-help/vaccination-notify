from binascii import unhexlify
from datetime import datetime, timedelta

from celery.utils.log import get_task_logger
from flask import current_app
from sqlalchemy import and_

from vacnotify import celery
from vacnotify.database import transaction
from vacnotify.models import GroupSubscription, Status, SpotSubscription
from vacnotify.utils import remove_pii

logging = get_task_logger(__name__)


@celery.task(ignore_result=True)
def clear_db_unconfirmed():
    now = datetime.now()
    notification_clear_time = timedelta(seconds=current_app.config["NOTIFICATION_UNCONFIRMED_CLEAR"])
    to_clear_group = GroupSubscription.query.filter(and_(GroupSubscription.status == Status.UNCONFIRMED,
                                                         GroupSubscription.created_at < now - notification_clear_time)).all()
    to_clear_spot = SpotSubscription.query.filter(and_(SpotSubscription.status == Status.UNCONFIRMED,
                                                       SpotSubscription.created_at < now - notification_clear_time)).all()
    logging.info(f"Clearing {len(to_clear_group)} group notification subscriptions and {len(to_clear_spot)} spot notification subscriptions.")
    to_clear = set(map(lambda subscription: f"[{subscription.id}] {remove_pii(subscription.email)}", to_clear_spot + to_clear_group))
    with transaction() as t:
        for group_sub in to_clear_group:
            t.delete(group_sub)
        for spot_sub in to_clear_spot:
            t.delete(spot_sub)
    logging.info(f"Cleared {to_clear}")


@celery.task(ignore_result=True)
def clear_db_push(secret):
    secret_bytes = unhexlify(secret)
    to_clear_group = GroupSubscription.query.filter_by(secret=secret_bytes).first()
    to_clear_spot = SpotSubscription.query.filter_by(secret=secret_bytes).first()
    with transaction() as t:
        if to_clear_group:
            t.delete(to_clear_group)
        if to_clear_spot:
            t.delete(to_clear_spot)
    logging.info(f"Cleared expired PUSH subscription")
