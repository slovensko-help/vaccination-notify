import json
from typing import Mapping, List

from flask import url_for
from pywebpush import webpush, WebPushException
from celery.utils.log import get_task_logger
from vacnotify import celery, vapid_privkey, vapid_claims
from vacnotify.tasks.maintenance import clear_db_push


logging = get_task_logger(__name__)


@celery.task(ignore_result=True)
def push_notification_spot(subscription_info, secret, cities_free: Mapping):
    actions = [
        {"action": "register",
         "title": "Zaregistrovať sa",
         "icon": url_for("main.static", filename="edit.svg")},
        {"action": "places",
         "title": "Voľné termíny",
         "icon": url_for("main.static", filename="calendar.svg")},
        {"action": "unsubsribe",
         "title": "Zrušiť odber",
         "icon": url_for("main.static", filename="bell-slash.svg")},
    ]
    action_map = {
        "register": "https://www.old.korona.gov.sk/covid-19-vaccination-form.php",
        "places": url_for("main.spot_subscribe", _anchor="places-table"),
        "unsubscribe": url_for("main.spot_unsubscribe", secret=secret)
    }
    try:
        webpush(subscription_info=subscription_info,
                data=json.dumps({"action": "notifySpots",
                                 "body": "V nasledujúcich mestách sú voľné termíny: " +
                                         ", ".join(f"{name} ({free})" for name, free in cities_free.items()) + ".",
                                 "icon": url_for('main.static', filename="virus.svg"),
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
def push_notification_group(subscription_info, secret, new_groups: List[str]):
    text = "Vo formulári na registráciu na očkovanie"
    if len(new_groups) > 1:
        text += " pribudli nové skupiny"
    else:
        text += " pribudla nová skupina"
    text += " ľudí na očkovanie: " + ", ".join(new_groups)

    actions = [
        {"action": "register",
         "title": "Zaregistrovať sa",
         "icon": url_for("main.static", filename="edit.svg")},
        {"action": "unsubsribe",
         "title": "Zrušiť odber",
         "icon": url_for("main.static", filename="bell-slash.svg")},
    ]
    action_map = {
        "register": "https://www.old.korona.gov.sk/covid-19-vaccination-form.php",
        "unsubscribe": url_for("main.group_unsubscribe", secret=secret)
    }
    try:
        webpush(subscription_info=subscription_info,
                data=json.dumps({"action": "notifyGroups",
                                 "body": text,
                                 "icon": url_for('main.static', filename="virus.svg"),
                                 "actions": actions,
                                 "actionMap": action_map}),
                vapid_private_key=vapid_privkey,
                vapid_claims=vapid_claims)
    except WebPushException as e:
        if e.response is not None and e.response.status_code == 410:
            clear_db_push.delay(secret)
        else:
            logging.error(e)
