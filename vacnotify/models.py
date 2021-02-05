from enum import Enum, auto
from operator import attrgetter

from vacnotify import db

group_db = db.Table("group_map", db.metadata,
                    db.Column("subscription_id", db.Integer, db.ForeignKey("group_subscription.id"), primary_key=True),
                    db.Column("group_id", db.Integer, db.ForeignKey("eligibility_group.id"), primary_key=True)
                    )

city_db = db.Table("city_map", db.metadata,
                   db.Column("subscription_id", db.Integer, db.ForeignKey("spot_subscription.id"), primary_key=True),
                   db.Column("city_id", db.Integer, db.ForeignKey("vaccination_city.id"), primary_key=True)
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
    # city <- backref
    city_id = db.Column(db.Integer, db.ForeignKey("vaccination_city.id"), nullable=False)
    street_name = db.Column(db.String(64))
    street_number = db.Column(db.String(64))
    online = db.Column(db.Boolean)
    free = db.Column(db.Integer)
    days = db.relationship("VaccinationDay", backref="place", lazy=True)

    def __init__(self, nczi_id: int, title: str, longitude: float, latitude: float,
                 city, street_name: str, street_number: str, online: bool, free: int):
        self.nczi_id = nczi_id
        self.title = title
        self.longitude = longitude
        self.latitude = latitude
        self.city = city
        self.street_name = street_name
        self.street_number = street_number
        self.online = online
        self.free = free


class VaccinationCity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    places = db.relationship("VaccinationPlace", backref="city", lazy="joined")

    def __init__(self, name: str):
        self.name = name

    @property
    def free(self):
        return sum(map(attrgetter("free"), self.places))

    @property
    def free_online(self):
        return sum(map(lambda place: place.free if place.online else 0, self.places))

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"VaccinationCity({self.name})"


class GroupSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128))
    created_at = db.Column(db.DateTime)
    secret = db.Column(db.LargeBinary(16))
    status = db.Column(db.Enum(Status))
    known_groups = db.relationship("EligibilityGroup", secondary=group_db)
    last_notification_at = db.Column(db.DateTime)

    def __init__(self, email: str, secret: secret, created_at, known_groups):
        self.email = email
        self.secret = secret
        self.status = Status.UNCONFIRMED
        self.created_at = created_at
        self.known_groups = known_groups


class SpotSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128))
    created_at = db.Column(db.DateTime)
    secret = db.Column(db.LargeBinary(16))
    status = db.Column(db.Enum(Status))
    cities = db.relationship("VaccinationCity", secondary=city_db)
    last_notification_at = db.Column(db.DateTime)

    def __init__(self, email: str, secret: bytes, created_at, tracked_cities):
        self.email = email
        self.secret = secret
        self.status = Status.UNCONFIRMED
        self.created_at = created_at
        self.cities = tracked_cities


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
