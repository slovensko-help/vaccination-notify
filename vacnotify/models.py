from enum import Enum, auto

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


class EligibilityGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(16))
    item_description = db.Column(db.String(256))


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


class GroupSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128))
    secret = db.Column(db.LargeBinary(16))
    status = db.Column(db.Enum(Status))
    known_groups = db.relationship("EligibilityGroup", secondary=group_db)


class SpotSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128))
    secret = db.Column(db.LargeBinary(16))
    status = db.Column(db.Enum(Status))
    places = db.relationship("VaccinationPlace", secondary=place_db)
