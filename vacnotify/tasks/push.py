import json
from typing import Mapping, List

from flask import url_for
from pywebpush import webpush, WebPushException
from celery.utils.log import get_task_logger
from vacnotify import celery, vapid_privkey, vapid_claims


logging = get_task_logger(__name__)


@celery.task(ignore_result=True)
def push_notification_spot(subscription_info, cities_free: Mapping):
    try:
        webpush(subscription_info=subscription_info,
                data=json.dumps({"action": "notifySpots",
                                 "body": "V nasledujúcich mestách sú voľné termíny: " +
                                         ", ".join(f"{name} ({free})" for name, free in cities_free.items()) + ".",
                                 "icon": url_for('.static', filename="virus.svg")}),
                vapid_private_key=vapid_privkey,
                vapid_claims=vapid_claims)
    except WebPushException as e:
        logging.error(e)


@celery.task(ignore_result=True)
def push_notification_group(subscription_info, new_groups: List[str]):
    text = "Vo formulári na registráciu na očkovanie"
    if len(new_groups) > 1:
        text += " pribudli nové skupiny"
    else:
        text += " pribudla nová skupina"
    text += " ľudí na očkovanie: " + ", ".join(new_groups)
    try:
        webpush(subscription_info=subscription_info,
                data=json.dumps({"action": "notifyGroups",
                                 "body": text,
                                 "icon": url_for('.static', filename="virus.svg")}),
                vapid_private_key=vapid_privkey,
                vapid_claims=vapid_claims)
    except WebPushException as e:
        logging.error(str(e))
