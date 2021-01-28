import random
from binascii import hexlify

import requests

from datetime import date, datetime, timedelta
from typing import Set, Mapping, List
from celery.utils.log import get_task_logger
from flask import render_template, current_app
from flask_mail import Message
from sqlalchemy import and_, or_, not_

from vacnotify import celery, mail, useragents
from vacnotify.database import transaction
from vacnotify.models import EligibilityGroup, VaccinationPlace, VaccinationDay, GroupSubscription, SpotSubscription, \
    Status
from operator import attrgetter, itemgetter

logging = get_task_logger(__name__)

GROUPS_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_vaccination_groups"
PLACES_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_driveins_vacc"
QUERY_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/validate_drivein_times_vacc"


@celery.task(ignore_result=True)
def email_confirmation(email: str, secret: str, subscription_type: str):
    if subscription_type not in ("group", "spot"):
        raise ValueError
    html = render_template("email/confirm.html.jinja2", secret=secret, type=subscription_type)
    msg = Message("Potvrdenie odberu notifikácii", recipients=[email], html=html)
    mail.send(msg)


@celery.task(ignore_result=True)
def email_notification_group(email: str, secret: str, new_groups: List[str]):
    html = render_template("email/notification_group.html.jinja2", secret=secret, new_groups=new_groups)
    msg = Message("Nová skupina na očkovanie", recipients=[email], html=html)
    mail.send(msg)


@celery.task(ignore_result=True)
def email_notification_spot(email: str, secret: str, cities_free: Mapping[str, int]):
    html = render_template("email/notification_spot.html.jinja2", secret=secret, cities_free=cities_free)
    msg = Message("Voľné miesta na očkovanie", recipients=[email], html=html)
    mail.send(msg)


@celery.task(ignore_result=True)
def run():
    s = requests.Session()
    s.headers["User-Agent"] = random.choice(useragents)

    # Get the new groups.
    groups_resp = s.get(GROUPS_URL)
    if groups_resp.status_code != 200:
        logging.error(f"Couldn't get groups -> {groups_resp.status_code}")
    else:
        group_payload = groups_resp.json()["payload"]
        current_groups = EligibilityGroup.query.all()
        current_group_ids = set(map(attrgetter("item_id"), current_groups))
        new_groups = list(filter(lambda group: group["item_code"] not in current_group_ids, group_payload))
        if new_groups:
            logging.info(f"Found new groups: {len(new_groups)}")
            with transaction() as t:
                for new_group in new_groups:
                    group = EligibilityGroup(new_group["item_code"], new_group["item_description_ui"])
                    t.add(group)
        else:
            logging.info("No new groups")

    # Update the vaccination places.
    places_resp = s.get(PLACES_URL)
    if places_resp.status_code != 200:
        logging.error(f"Couldn't get places -> {places_resp.status_code}")
    else:
        places_payload = places_resp.json()["payload"]
        current_places = VaccinationPlace.query.all()
        place_ids: Set[str] = set(map(itemgetter("id"), places_payload))
        current_place_nczi_ids: Set[int] = set(map(attrgetter("nczi_id"), current_places))
        # Update places to online.
        online_places = list(filter(lambda place: str(place.nczi_id) in place_ids, current_places))
        with transaction():
            for online_place in online_places:
                online_place.online = True

        # Add new places.
        new_places = list(filter(lambda place: int(place["id"]) not in current_place_nczi_ids, places_payload))
        if new_places:
            logging.info(f"Found new places: {len(new_places)}")
            with transaction() as t:
                for new_place in new_places:
                    place = VaccinationPlace(int(new_place["id"]), new_place["title"], float(new_place["longitude"]),
                                             float(new_place["latitude"]), new_place["city"], new_place["street_name"],
                                             new_place["street_number"], True, 0)
                    t.add(place)
        else:
            logging.info("No new places")

        # Set places to offline.
        offline_places = list(filter(lambda place: str(place.nczi_id) not in place_ids and place.online, current_places))
        if offline_places:
            logging.info(f"Found some places that are now offline: {len(offline_places)}")
            with transaction():
                for off_place in offline_places:
                    off_place.online = False
        else:
            logging.info("All current places are online")

    # Update the free spots in vaccination places.
    current_places = VaccinationPlace.query.all()
    total_free = 0
    total_free_online = 0
    for place in current_places:
        free_resp = s.post(QUERY_URL, json={"drivein_id": str(place.nczi_id)})
        if free_resp.status_code != 200:
            logging.error(f"Couldn't get free spots -> {free_resp.status_code}")
        else:
            free_payload = free_resp.json()["payload"]
            free = 0
            days = []
            previous_days = set(place.days)
            for line in free_payload:
                day_date = date.fromisoformat(line["c_date"])
                open = line["is_closed"] != "1"
                try:
                    capacity = int(line["free_capacity"])
                except Exception:
                    capacity = 0
                day = VaccinationDay.query.filter_by(date=day_date, place=place).first()
                if day is None:
                    day = VaccinationDay(day_date, open, capacity, place)
                day.open = open
                day.capacity = capacity
                days.append(day)
                if capacity > 0 and open:
                    free += capacity
            if free:
                total_free += free
                total_free_online += free if place.online else 0
                logging.info(f"Found free spots: {free} at {place.title} and they are {'online' if place.online else 'offline'}")
            deleted_days = previous_days - set(days)
            with transaction() as t:
                if deleted_days:
                    for deleted_day in deleted_days:
                        t.delete(deleted_day)
                place.days = days
                place.free = free
    logging.info(f"Total free spots (online): {total_free} ({total_free_online})")

    # Send out the group notifications.
    all_groups = EligibilityGroup.query.all()
    now = datetime.now()
    group_backoff_time = timedelta(seconds=current_app.config["GROUP_NOTIFICATION_BACKOFF"])
    to_notify_groups = set()
    for group in all_groups:
        group_notifications = GroupSubscription.query.join(GroupSubscription.known_groups).filter(
            and_(GroupSubscription.status == Status.CONFIRMED,
                 not_(EligibilityGroup.id == group.id),
                 or_(GroupSubscription.last_notification_at.is_(None),
                     GroupSubscription.last_notification_at < now - group_backoff_time))).all()
        to_notify_groups.update(group_notifications)
    for subscription in to_notify_groups:
        logging.info(f"Sending group notification to {subscription.email}.")
        new_subscription_groups = set(map(attrgetter("item_description"), set(all_groups) - set(subscription.known_groups)))
        with transaction():
            email_notification_group.delay(subscription.email, hexlify(subscription.secret).decode(), list(new_subscription_groups))
            subscription.last_notification_at = now
            subscription.known_groups = all_groups

    # Send out the spot notifications.
    now = datetime.now()
    spot_backoff_time = timedelta(seconds=current_app.config["SPOT_NOTIFICATION_BACKOFF"])
    to_notify_spots = SpotSubscription.query.join(SpotSubscription.places).filter(
        and_(VaccinationPlace.free > 0,
             VaccinationPlace.online,
             SpotSubscription.status == Status.CONFIRMED,
             or_(SpotSubscription.last_notification_at.is_(None),
                 SpotSubscription.last_notification_at < now - spot_backoff_time))).all()
    for subscription in to_notify_spots:
        logging.info(f"Sending spot notification to {subscription.email}.")
        new_subscription_cities = {}
        for place in subscription.places:
            if place.free > 0 and place.online:
                new_subscription_cities.setdefault(place.city, 0)
                new_subscription_cities[place.city] += place.free
        with transaction():
            email_notification_spot.delay(subscription.email, hexlify(subscription.secret).decode(), new_subscription_cities)
            subscription.last_notification_at = now
