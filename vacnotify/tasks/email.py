from typing import List, Mapping

from flask import render_template, url_for
from flask_mail import Message

from vacnotify import celery, mail


@celery.task(ignore_result=True)
def email_confirmation(email: str, secret: str, subscription_type: str):
    if subscription_type not in ("group", "spot", "both"):
        raise ValueError
    title_suffix = {
        "group": " - Nová skupina",
        "spot": " - Voľné miesta",
        "both": ""
    }
    html = render_template("email/confirm.html.jinja2", secret=secret, type=subscription_type)
    msg = Message("Potvrdenie odberu notifikácii" + title_suffix[subscription_type], recipients=[email], html=html,
                  extra_headers={"List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                                 "List-Unsubscribe": "<" + url_for(f"main.{subscription_type}_unsubscribe", secret=secret) + ">"})
    mail.send(msg)


@celery.task(ignore_result=True)
def email_notification_group(email: str, secret: str, new_groups: List[str]):
    html = render_template("email/notification_group.html.jinja2", secret=secret, new_groups=new_groups)
    msg = Message("Nová skupina na očkovanie", recipients=[email], html=html,
                  extra_headers={"List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                                 "List-Unsubscribe": "<" + url_for("main.group_unsubscribe", secret=secret) + ">"})
    mail.send(msg)


@celery.task(ignore_result=True)
def email_notification_spot(email: str, secret: str, cities_free: Mapping[str, int]):
    html = render_template("email/notification_spot.html.jinja2", secret=secret, cities_free=cities_free)
    msg = Message("Voľné miesta na očkovanie", recipients=[email], html=html,
                  extra_headers={"List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                                 "List-Unsubscribe": "<" + url_for("main.spot_unsubscribe", secret=secret) + ">"})
    mail.send(msg)
