import requests
from celery.utils.log import get_task_logger
from vacnotify import celery
from vacnotify.database import transaction
from vacnotify.models import EligibilityGroup, VaccinationPlace
from operator import attrgetter, itemgetter

logging = get_task_logger(__name__)

GROUPS_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_vaccination_groups"
PLACES_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_driveins_vacc"
QUERY_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/validate_drivein_times_vacc"


@celery.task(ignore_result=True)
def run():
    s = requests.Session()

    # Get the new groups.
    groups_resp = s.get(GROUPS_URL)
    if groups_resp.status_code != 200:
        logging.error(f"Couldn't get groups -> {groups_resp.status_code}")
    else:
        group_payload = groups_resp.json()["payload"]
        current_groups = EligibilityGroup.query.all()
        current_group_ids = set(map(attrgetter("item_id"), current_groups))
        new_groups = filter(lambda group: group["item_code"] not in current_group_ids, group_payload)
        if new_groups:
            logging.info(f"Found new groups")
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
        place_ids = set(map(itemgetter("id"), places_payload))
        current_place_nczi_ids = set(map(attrgetter("nczi_id"), current_places))
        # Update places to online.
        online_places = filter(lambda place: place.nczi_id in place_ids, current_places)
        with transaction():
            for online_place in online_places:
                online_place.online = True

        # Add new places.
        new_places = filter(lambda place: place["id"] not in current_place_nczi_ids, places_payload)
        if new_places:
            logging.info("Found new places")
            with transaction() as t:
                for new_place in new_places:
                    place = VaccinationPlace(new_place["id"], new_place["title"], float(new_place["longitude"]),
                                             float(new_place["latitude"]), new_place["city"], new_place["street_name"],
                                             new_place["street_number"], True)
                    t.add(place)
        else:
            logging.info("No new places")

        # Set places to offline.
        offline_places = filter(lambda place: place.nczi_id not in place_ids, current_places)
        if offline_places:
            logging.info("Found some places that are now offline")
            with transaction():
                for off_place in offline_places:
                    off_place.online = False
        else:
            logging.info("All current places are online")

    # Update the free spots in vaccination places.
    current_places = VaccinationPlace.query.all()
    for place in current_places:
        free_resp = s.get(QUERY_URL, json={"drivein_id": str(place.nczi_id)})
        if free_resp.status_code != 200:
            logging.error(f"Couldn't get free spots -> {free_resp.status_code}")
        else:
            free_payload = free_resp.json()["payload"]
            free = 0
            for line in free_payload:
                if line["free_capacity"] != "0" and line["is_closed"] != "1":
                    try:
                        amount = int(line["free_capacity"])
                    except Exception:
                        # Handle possibly weird number format by NCZI gracefully and actually notice anything different from 0.
                        amount = 1
                    if amount > 0:
                        free += amount
            with transaction():
                place.free = free

