from enum import Enum, auto
import secrets
from vacnotify import db

group_db = db.Table("group_map", db.metadata,
                    db.Column("subscription_id", db.Integer, db.ForeignKey("group_subscription.id"), primary_key=True),
                    db.Column("group_id", db.Integer, db.ForeignKey("eligibility_group.id"), primary_key=True)
                    )

place_db = db.Table("places_map", db.metadata,
                    db.Column("subscription_id", db.Integer, db.ForeignKey("spot_subscription.id"), primary_key=True),
                    db.Column("place_id", db.Integer, db.ForeignKey("vaccination_place.id"), primary_key=True)
                    )


class Status(Enum):
    UNCONFIRMED = auto()
    CONFIRMED = auto()


class VaccinationDay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    open = db.Column(db.Boolean)
    capacity = db.Column(db.Integer)
    place_id = db.Column(db.Integer, db.ForeignKey("vaccination_place.id"), nullable=False)
    # <- place (dynamic backref)

    def __init__(self, date, open: bool, capacity: int, place):
        self.date = date
        self.open = open
        self.capacity = capacity
        self.place = place


class EligibilityGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(16))
    item_description = db.Column(db.String(256))

    def __init__(self, item_id: str, item_description: str):
        self.item_id = item_id
        self.item_description = item_description


class VaccinationPlace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nczi_id = db.Column(db.Integer)
    title = db.Column(db.String(128))
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    city = db.Column(db.String(64))
    street_name = db.Column(db.String(64))
    street_number = db.Column(db.String(64))
    online = db.Column(db.Boolean)
    free = db.Column(db.Integer)
    days = db.relationship("VaccinationDay", backref="place", lazy=True)

    def __init__(self, nczi_id: int, title: str, longitude: float, latitude: float,
                 city: str, street_name: str, street_number: str, online: bool, free: int):
        self.nczi_id = nczi_id
        self.title = title
        self.longitude = longitude
        self.latitude = latitude
        self.city = city
        self.street_name = street_name
        self.street_number = street_number
        self.online = online
        self.free = free


class GroupSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128))
    secret = db.Column(db.LargeBinary(16))
    status = db.Column(db.Enum(Status))
    known_groups = db.relationship("EligibilityGroup", secondary=group_db)
    last_notification_at = db.Column(db.DateTime)

    def __init__(self, email: str, known_groups):
        self.email = email
        self.secret = secrets.token_bytes(16)
        self.status = Status.UNCONFIRMED
        self.known_groups = known_groups


class SpotSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128))
    secret = db.Column(db.LargeBinary(16))
    status = db.Column(db.Enum(Status))
    places = db.relationship("VaccinationPlace", secondary=place_db)
    last_notification_at = db.Column(db.DateTime)

    def __init__(self, email: str, tracked_places):
        self.email = email
        self.secret = secrets.token_bytes(16)
        self.status = Status.UNCONFIRMED
        self.places = tracked_places


class VaccinationStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime)
    total_free_spots = db.Column(db.Integer)
    total_free_online_spots = db.Column(db.Integer)
    online_places = db.Column(db.Integer)
    total_places = db.Column(db.Integer)

    def __init__(self, datetime, total_free_spots: int, total_free_online_spots: int, online_places: int, total_places: int):
        self.datetime = datetime
        self.total_free_spots = total_free_spots
        self.total_free_online_spots = total_free_online_spots
        self.online_places = online_places
        self.total_places = total_places

    def __json__(self):
        return {key: getattr(self, key) for key in dir(self) if not key.startswith("_") and key not in ("metadata", "query", "query_class")}
