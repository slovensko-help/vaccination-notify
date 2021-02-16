import json
from binascii import hexlify
from typing import Mapping, List

from flask import url_for
from pywebpush import webpush, WebPushException
from celery.utils.log import get_task_logger
from vacnotify import celery, vapid_privkey, vapid_claims
from vacnotify.tasks.maintenance import clear_db_push


logging = get_task_logger(__name__)


@celery.task(ignore_result=True)
def push_notification(subscription_info, body: str):
    try:
        webpush(subscription_info=subscription_info,
                data=json.dumps({"action": "notify",
                                 "body": body,
                                 "icon": url_for('main.static', filename="img/virus.svg", _external=True),
                                 "actions": []}))
    except WebPushException as e:
        if e.response is not None and e.response.status_code == 410:
            logging.info(e)
        else:
            logging.error(e)


@celery.task(ignore_result=True)
def push_confirmation(subscription_info, secret: str, subscription_type: str):
    endpoint_map = {
        "group": "main.group_confirm",
        "spot": "main.spot_confirm",
        "both": "main.both_confirm"
    }
    endpoint = endpoint_map[subscription_type]
    try:
        webpush(subscription_info=subscription_info,
                data=json.dumps({"action": "confirm",
                                 "endpoint": url_for(endpoint, secret=secret, push=1)}),
                vapid_private_key=vapid_privkey,
                vapid_claims=vapid_claims)
    except WebPushException as e:
        if e.response is not None and e.response.status_code == 410:
            clear_db_push.delay(secret)
        else:
            logging.error(e)


@celery.task(ignore_result=True)
def push_notification_spot(subscription_info, secret: str, cities_free: Mapping):
    actions = [
        {"action": "register",
         "title": "Zaregistrovať sa",
         "icon": url_for("main.static", filename="img/edit.svg", _external=True)},
        {"action": "places",
         "title": "Voľné termíny",
         "icon": url_for("main.static", filename="img/calendar.svg", _external=True)},
        {"action": "unsubsribe",
         "title": "Zrušiť odber",
         "icon": url_for("main.static", filename="img/bell-slash.svg", _external=True)},
    ]
    action_map = {
        "register": "https://www.old.korona.gov.sk/covid-19-vaccination-form.php",
        "places": url_for("main.spot_subscribe", _anchor="places-table", _external=True),
        "unsubscribe": url_for("main.spot_unsubscribe", secret=secret, _external=True)
    }
    try:
        webpush(subscription_info=subscription_info,
                data=json.dumps({"action": "notifySpots",
                                 "body": "V nasledujúcich mestách sú voľné termíny: " +
                                         ", ".join(f"{name} ({free})" for name, free in cities_free.items()) + ".",
                                 "icon": url_for('main.static', filename="img/virus.svg", _external=True),
                                 "actions": actions,
                                 "actionMap": action_map}),
                vapid_private_key=vapid_privkey,
                vapid_claims=vapid_claims)
    except WebPushException as e:
        if e.response is not None and e.response.status_code == 410:
            clear_db_push.delay(secret)
        else:
            logging.error(e)


@celery.task(ignore_result=True)
def push_notification_group(subscription_info, secret: str, new_groups: List[str]):
    text = "Vo formulári na registráciu na očkovanie"
    if len(new_groups) > 1:
        text += " pribudli nové skupiny"
    else:
        text += " pribudla nová skupina"
    text += " ľudí na očkovanie: " + ", ".join(new_groups)

    actions = [
        {"action": "register",
         "title": "Zaregistrovať sa",
         "icon": url_for("main.static", filename="img/edit.svg", _external=True)},
        {"action": "unsubsribe",
         "title": "Zrušiť odber",
         "icon": url_for("main.static", filename="img/bell-slash.svg", _external=True)},
    ]
    action_map = {
        "register": "https://www.old.korona.gov.sk/covid-19-vaccination-form.php",
        "unsubscribe": url_for("main.group_unsubscribe", secret=secret, _external=True)
    }
    try:
        webpush(subscription_info=subscription_info,
                data=json.dumps({"action": "notifyGroups",
                                 "body": text,
                                 "icon": url_for('main.static', filename="img/virus.svg", _external=True),
                                 "actions": actions,
                                 "actionMap": action_map}),
                vapid_private_key=vapid_privkey,
                vapid_claims=vapid_claims)
    except WebPushException as e:
        if e.response is not None and e.response.status_code == 410:
            clear_db_push.delay(secret)
        else:
            logging.error(e)
