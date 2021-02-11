import json
import sys
import time
import requests

from binascii import hexlify
from operator import attrgetter, itemgetter
from datetime import date, datetime, timedelta
from typing import Set, List

from celery.utils.log import get_task_logger
from flask import current_app
from requests.utils import default_user_agent
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload
from stem import Signal
from stem.control import Controller
from stem.util.log import get_logger as get_stem_logger

from vacnotify import celery
from vacnotify.database import transaction
from vacnotify.models import EligibilityGroup, VaccinationPlace, VaccinationDay, GroupSubscription, SpotSubscription, \
    Status, VaccinationStats, VaccinationCity, SubscriptionStats
from vacnotify.tasks.email import email_notification_group, email_notification_spot
from vacnotify.tasks.push import push_notification_group, push_notification_spot
from vacnotify.utils import remove_pii

logging = get_task_logger(__name__)
get_stem_logger().propagate = False


class RetrySession(object):
    def __init__(self, retries: int = 5, timeout: int = 5):
        self.retries = retries
        self.timeout = timeout
        self.sess = None
        self.reset_session()

    def reset_session(self):
        self.sess = requests.Session()
        if current_app.config["TOR_USE"]:
            self.sess.proxies = {"http": current_app.config["TOR_SOCKS"],
                                 "https": current_app.config["TOR_SOCKS"]}
            with Controller.from_port(address=current_app.config["TOR_CONTROL_ADDRESS"],
                                      port=current_app.config["TOR_CONTROL_PORT"]) as controller:
                controller.authenticate(password=current_app.config["TOR_CONTROL_PASSWORD"])
                controller.signal(Signal.NEWNYM)
        self.sess.headers["User-Agent"] = f"vaccination-notify/{current_app.env} {default_user_agent()} Python/{'.'.join(map(str, sys.version_info[:3]))}"
        logging.info("Restarted session.")

    def get(self, *args, **kwargs):
        for i in range(self.retries):
            try:
                return self.sess.get(*args, **kwargs, timeout=self.timeout)
            except Exception as e:
                logging.info(f"Got {e}")
                if i != self.retries - 1:
                    self.reset_session()
                else:
                    raise e
                time.sleep(current_app.config["QUERY_DELAY"])

    def post(self, *args, **kwargs):
        for i in range(self.retries):
            try:
                return self.sess.post(*args, **kwargs, timeout=self.timeout)
            except Exception as e:
                logging.info(f"Got {e}")
                if i != self.retries - 1:
                    self.reset_session()
                else:
                    raise e
                time.sleep(current_app.config["QUERY_DELAY"])


class NCZI(object):
    def __init__(self, session):
        self.session = session
        self._urls = {
            "nczi": {
                "groups": (current_app.config["NCZI_GROUPS_URL"], "GET"),
                "places": (current_app.config["NCZI_PLACES_URL"], "GET"),
                "place": (current_app.config["NCZI_QUERY_URL"], "POST"),
                "places_all": (current_app.config["NCZI_PLACES_ALL_URL"], "GET")
            },
            "proxy": {
                "groups": (current_app.config["PROXY_GROUPS_URL"], "GET"),
                "places": (current_app.config["PROXY_PLACES_URL"], "GET"),
                "place": (current_app.config["PROXY_QUERY_URL"], "GET"),
                "places_all": (current_app.config["PROXY_PLACES_ALL_URL"], "GET")
            }
        }[current_app.config["API_USE"]]

    def request(self, url, method, **kwargs) -> requests.Response:
        if method == "GET":
            return self.session.get(url, params=kwargs)
        if method == "POST":
            return self.session.post(url, json=kwargs)

    def get_groups(self) -> requests.Response:
        return self.request(*self._urls["groups"])

    def get_places(self) -> requests.Response:
        return self.request(*self._urls["places"])

    def get_place(self, nczi_id: int) -> requests.Response:
        return self.request(*self._urls["place"], drivein_id=str(nczi_id))

    def get_places_full(self) -> requests.Response:
        return self.request(*self._urls["places_all"])


def query_groups(s):
    # Get the new groups.
    groups_resp = s.get_groups()
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


def query_places(s):
    # Update the vaccination places.
    places_resp = s.get_places()
    if places_resp.status_code != 200:
        logging.error(f"Couldn't get places -> {places_resp.status_code}")
    else:
        places_payload = places_resp.json()["payload"]
        # Add new cities if any.
        current_cities = VaccinationCity.query.all()
        city_map = {city.name: city for city in current_cities}
        current_city_names: Set[str] = set(map(attrgetter("name"), current_cities))
        city_names: Set[str] = set(map(itemgetter("city"), places_payload))
        new_city_names = city_names - current_city_names
        if new_city_names:
            logging.info(f"Found some new cities: {new_city_names}")
            with transaction() as t:
                for city_name in new_city_names:
                    city = VaccinationCity(city_name)
                    t.add(city)
                    city_map[city_name] = city
        else:
            logging.info("No new cities")

        current_places = VaccinationPlace.query.all()
        place_ids: Set[str] = set(map(itemgetter("id"), places_payload))
        place_map = {int(place["id"]): place for place in places_payload}
        current_place_nczi_ids: Set[int] = set(map(attrgetter("nczi_id"), current_places))
        # Update places to online.
        online_places: List[VaccinationPlace] = list(filter(lambda place: str(place.nczi_id) in place_ids, current_places))
        with transaction():
            for online_place in online_places:
                nczi_place = place_map[online_place.nczi_id]
                online_place.title = nczi_place["title"]
                online_place.longitude = float(nczi_place["longitude"])
                online_place.latitude = float(nczi_place["latitude"])
                online_place.city = city_map[nczi_place["city"]]
                online_place.street_name = nczi_place["street_name"]
                online_place.street_number = nczi_place["street_number"]
                online_place.online = True

        # Add new places.
        new_places = list(filter(lambda place: int(place["id"]) not in current_place_nczi_ids, places_payload))
        if new_places:
            logging.info(f"Found new places: {len(new_places)}")
            with transaction() as t:
                for new_place in new_places:
                    place = VaccinationPlace(int(new_place["id"]), new_place["title"], float(new_place["longitude"]),
                                             float(new_place["latitude"]), city_map[new_place["city"]], new_place["street_name"],
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


def query_places_all(s):
    # Update the free spots in vaccination places.
    current_places = VaccinationPlace.query.options(joinedload(VaccinationPlace.days)).all()
    total_free = 0
    total_free_online = 0
    for place in current_places:
        free_resp = s.get_place(place.nczi_id)
        time.sleep(current_app.config["QUERY_DELAY"])
        if free_resp.status_code != 200:
            logging.error(f"Couldn't get free spots -> {free_resp.status_code}")
        else:
            free_payload = free_resp.json()["payload"]
            free = 0
            days = []
            previous_days = {day.date: day for day in place.days}
            for line in free_payload:
                day_date = date.fromisoformat(line["c_date"])
                open = line["is_closed"] != "1"
                try:
                    capacity = int(line["free_capacity"])
                except Exception:
                    capacity = 0
                day = previous_days.get(day_date)
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
            deleted_days = set(previous_days.values()) - set(days)
            with transaction() as t:
                if deleted_days:
                    for deleted_day in deleted_days:
                        t.delete(deleted_day)
                place.days = days
                place.free = free
    logging.info(f"Total free spots (online): {total_free} ({total_free_online})")
    total_places = len(current_places)
    online_places = len(list(filter(attrgetter("online"), current_places)))
    logging.info(f"Total places (online): {total_places} ({online_places})")
    return {
        "total_free_spots": total_free,
        "total_free_online_spots": total_free_online,
        "total_places": total_places,
        "online_places": online_places
    }


def query_places_aggregate(s):
    # Update the places and free spots using the aggregate API
    current_places = VaccinationPlace.query.all()
    total_free = 0
    total_free_online = 0
    places_resp = s.get_places_full()
    if places_resp.status_code != 200:
        logging.error(f"Couldn't get full places -> {places_resp.status_code}")
    else:
        places_payload = places_resp.json()["payload"]
        # Add new cities if any.
        current_cities = VaccinationCity.query.all()
        city_map = {city.name: city for city in current_cities}
        current_city_names: Set[str] = set(map(attrgetter("name"), current_cities))
        city_names: Set[str] = set(map(itemgetter("city"), places_payload))
        new_city_names = city_names - current_city_names
        if new_city_names:
            logging.info(f"Found some new cities: {new_city_names}")
            with transaction() as t:
                for city_name in new_city_names:
                    city = VaccinationCity(city_name)
                    t.add(city)
                    city_map[city_name] = city
        else:
            logging.info("No new cities")

        place_ids: Set[str] = set(map(itemgetter("id"), places_payload))
        place_map = {int(place["id"]): place for place in places_payload}
        current_place_nczi_ids: Set[int] = set(map(attrgetter("nczi_id"), current_places))
        # Update places to online.
        online_places: List[VaccinationPlace] = list(filter(lambda place: str(place.nczi_id) in place_ids, current_places))
        with transaction():
            for online_place in online_places:
                nczi_place = place_map[online_place.nczi_id]
                online_place.title = nczi_place["title"]
                online_place.longitude = float(nczi_place["longitude"])
                online_place.latitude = float(nczi_place["latitude"])
                online_place.city = city_map[nczi_place["city"]]
                online_place.street_name = nczi_place["street_name"]
                online_place.street_number = nczi_place["street_number"]
                online_place.online = True

        # Add new places.
        new_places = list(filter(lambda place: int(place["id"]) not in current_place_nczi_ids, places_payload))
        if new_places:
            logging.info(f"Found new places: {len(new_places)}")
            with transaction() as t:
                for new_place in new_places:
                    place = VaccinationPlace(int(new_place["id"]), new_place["title"], float(new_place["longitude"]),
                                             float(new_place["latitude"]), city_map[new_place["city"]], new_place["street_name"],
                                             new_place["street_number"], True, 0)
                    t.add(place)
        else:
            logging.info("No new places")

        # Set places to offline.
        offline_places = list(
            filter(lambda place: str(place.nczi_id) not in place_ids and place.online, current_places))
        if offline_places:
            logging.info(f"Found some places that are now offline: {len(offline_places)}")
            with transaction():
                for off_place in offline_places:
                    off_place.online = False
        else:
            logging.info("All current places are online")

        current_places = VaccinationPlace.query.options(joinedload(VaccinationPlace.days)).all()
        for place in current_places:
            if place.nczi_id not in place_map:
                continue
            free_payload = place_map[place.nczi_id]["calendar_data"]
            free = 0
            days = []
            previous_days = {day.date: day for day in place.days}
            for line in free_payload:
                day_date = date.fromisoformat(line["c_date"])
                open = line["is_closed"] != "1"
                try:
                    capacity = int(line["free_capacity"])
                except Exception:
                    capacity = 0
                day = previous_days.get(day_date)
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
            deleted_days = set(previous_days.values()) - set(days)
            with transaction() as t:
                if deleted_days:
                    for deleted_day in deleted_days:
                        t.delete(deleted_day)
                place.days = days
                place.free = free
    logging.info(f"Total free spots (online): {total_free} ({total_free_online})")
    total_places = len(current_places)
    online_places = len(list(filter(attrgetter("online"), current_places)))
    logging.info(f"Total places (online): {total_places} ({online_places})")
    return {
        "total_free_spots": total_free,
        "total_free_online_spots": total_free_online,
        "total_places": total_places,
        "online_places": online_places
    }


def notify_groups():
    # Send out the group notifications.
    all_groups = EligibilityGroup.query.all()
    now = datetime.now()
    group_backoff_time = timedelta(seconds=current_app.config["GROUP_NOTIFICATION_BACKOFF"])
    group_subs_email = GroupSubscription.query.options(joinedload(GroupSubscription.known_groups)).filter(
        and_(GroupSubscription.status == Status.CONFIRMED,
             GroupSubscription.push_sub.is_(None),
             or_(GroupSubscription.last_notification_at.is_(None),
                 GroupSubscription.last_notification_at < now - group_backoff_time))).all()
    for subscription in group_subs_email:
        new_subscription_groups = set(map(attrgetter("item_description"), set(all_groups) - set(subscription.known_groups)))
        if new_subscription_groups:
            logging.info(f"Sending group notification to [{subscription.id}] {remove_pii(subscription.email)}.")
            with transaction():
                email_notification_group.delay(subscription.email, hexlify(subscription.secret).decode(), list(new_subscription_groups))
                subscription.last_notification_at = now
                subscription.known_groups = all_groups
    group_subs_push = GroupSubscription.query.options(joinedload(GroupSubscription.known_groups)).filter(
        and_(GroupSubscription.status == Status.CONFIRMED,
             GroupSubscription.email.is_(None),
             or_(GroupSubscription.last_notification_at.is_(None),
                 GroupSubscription.last_notification_at < now - group_backoff_time))).all()
    for subscription in group_subs_push:
        new_subscription_groups = set(map(attrgetter("item_description"), set(all_groups) - set(subscription.known_groups)))
        if new_subscription_groups:
            logging.info(f"Sending group notification to [{subscription.id}].")
            with transaction():
                push_notification_group.delay(json.loads(subscription.push_sub), hexlify(subscription.secret).decode(), list(new_subscription_groups))
                subscription.last_notification_at = now
                subscription.known_groups = all_groups


def notify_spots():
    # Send out the spot notifications.
    now = datetime.now()
    spot_backoff_time = timedelta(seconds=current_app.config["SPOT_NOTIFICATION_BACKOFF"])
    spot_subs_free = SpotSubscription.query.options(joinedload(SpotSubscription.known_cities)).join(SpotSubscription.cities).join(VaccinationCity.places).filter(
        and_(VaccinationPlace.free > 0,
             VaccinationPlace.online,
             SpotSubscription.status == Status.CONFIRMED,
             SpotSubscription.push_sub.is_(None),
             or_(SpotSubscription.last_notification_at.is_(None),
                 SpotSubscription.last_notification_at < now - spot_backoff_time))).all()

    for subscription in spot_subs_free:
        free_cities = set(city for city in subscription.cities if city.free_online)
        if free_cities != set(subscription.known_cities) and free_cities:
            logging.info(f"Sending spot notification to [{subscription.id}] {remove_pii(subscription.email)}.")
            new_subscription_cities = {city.name: {
                "free": city.free_online,
                "places": [(place.title, place.free) for place in city.places if place.online and place.free]
            } for city in free_cities}
            with transaction():
                email_notification_spot.delay(subscription.email, hexlify(subscription.secret).decode(), new_subscription_cities)
                subscription.last_notification_at = now
                subscription.known_cities = list(free_cities)

    spot_subs_free_push = SpotSubscription.query.options(joinedload(SpotSubscription.known_cities)).join(SpotSubscription.cities).join(VaccinationCity.places).filter(
        and_(VaccinationPlace.free > 0,
             VaccinationPlace.online,
             SpotSubscription.status == Status.CONFIRMED,
             SpotSubscription.email.is_(None),
             or_(SpotSubscription.last_notification_at.is_(None),
                 SpotSubscription.last_notification_at < now - spot_backoff_time))).all()
    for subscription in spot_subs_free_push:
        free_cities = set(city for city in subscription.cities if city.free_online)
        if free_cities != set(subscription.known_cities) and free_cities:
            logging.info(f"Sending spot notification to [{subscription.id}].")
            new_subscription_cities = {city.name: city.free_online for city in free_cities}
            with transaction():
                push_notification_spot.delay(json.loads(subscription.push_sub), hexlify(subscription.secret).decode(), new_subscription_cities)
                subscription.last_notification_at = now
                subscription.known_cities = list(free_cities)


def compute_subscription_stats():
    spot_emails = set(SpotSubscription.query.with_entities(SpotSubscription.email).all())
    spot_top_id = SpotSubscription.query.order_by(SpotSubscription.id.desc()).with_entities(SpotSubscription.id).limit(1).scalar()
    group_emails = set(GroupSubscription.query.with_entities(GroupSubscription.email).all())
    group_top_id = GroupSubscription.query.order_by(GroupSubscription.id.desc()).with_entities(GroupSubscription.id).limit(1).scalar()
    return {
        "unique_emails": len(spot_emails | group_emails),
        "shared_emails": len(spot_emails & group_emails),
        "spot_subs_top_id": spot_top_id if spot_top_id is not None else 0,
        "spot_subs_confirmed": SpotSubscription.query.filter(SpotSubscription.status == Status.CONFIRMED).count(),
        "spot_subs_unconfirmed": SpotSubscription.query.filter(SpotSubscription.status == Status.UNCONFIRMED).count(),
        "group_subs_top_id": group_top_id if group_top_id is not None else 0,
        "group_subs_confirmed": GroupSubscription.query.filter(GroupSubscription.status == Status.CONFIRMED).count(),
        "group_subs_unconfirmed": GroupSubscription.query.filter(GroupSubscription.status == Status.UNCONFIRMED).count()
    }


@celery.task(ignore_result=True)
def run():
    s = NCZI(RetrySession())

    query_groups(s)
    time.sleep(current_app.config["QUERY_DELAY"])

    if current_app.config["API_USE_AGGREGATE"]:
        place_stats = query_places_aggregate(s)
    else:
        query_places(s)
        time.sleep(current_app.config["QUERY_DELAY"])
        place_stats = query_places_all(s)

    sub_stats = compute_subscription_stats()

    # Add stats
    now = datetime.now()
    with transaction() as t:
        t.add(VaccinationStats(now, **place_stats))
        t.add(SubscriptionStats(now, **sub_stats))

    notify_groups()
    notify_spots()

