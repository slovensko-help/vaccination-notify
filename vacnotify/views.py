import hashlib
import json
import locale
from binascii import unhexlify, hexlify
from datetime import datetime, timedelta
from operator import attrgetter

from flask import render_template, request, abort, current_app, jsonify, url_for
from sqlalchemy.orm import joinedload
from pywebpush import webpush, WebPushException

from vacnotify import vapid_pubkey as pubkey, vapid_privkey as privkey, vapid_claims as claims
from vacnotify.blueprint import main
from vacnotify.database import transaction
from vacnotify.models import EligibilityGroup, VaccinationPlace, GroupSubscription, Status, SpotSubscription, \
    VaccinationStats, VaccinationCity, SubscriptionStats
from vacnotify.forms import GroupSubscriptionForm, SpotSubscriptionForm
from vacnotify.tasks.email import email_confirmation
from vacnotify.utils import hcaptcha_required, sentry_untraced


@main.route("/")
def index():
    return render_template("index.html.jinja2")


@main.route("/privacy")
def privacy():
    return render_template("privacy_policy.html.jinja2")


@main.route("/stats")
def stats():
    vaccination_stats = VaccinationStats.query.filter(VaccinationStats.datetime > (datetime.now() - timedelta(days=7))).order_by(VaccinationStats.id.desc()).all()
    subscription_stats = SubscriptionStats.query.filter(SubscriptionStats.datetime > (datetime.now() - timedelta(days=7))).order_by(SubscriptionStats.id.desc()).all()

    return render_template("stats.html.jinja2", vaccination_stats=vaccination_stats, subscription_stats=subscription_stats,
                           current_vstats=vaccination_stats[0], current_sstats=subscription_stats[0])


@main.route("/groups/subscribe", methods=["GET", "POST"])
@hcaptcha_required("push_sub")
def group_subscribe():
    frm = GroupSubscriptionForm()
    if request.method == "GET" or not frm.validate_on_submit():
        last_stats = VaccinationStats.query.order_by(VaccinationStats.id.desc()).first()
        return render_template("subscribe_group.jinja2", form=frm, groups=EligibilityGroup.query.all(), last_stats=last_stats)
    else:
        if frm.validate_on_submit():
            if frm.email.data:
                # Email subscription
                email_exists = GroupSubscription.query.filter_by(email=frm.email.data).first() is not None
                if email_exists:
                    return render_template("error.html.jinja2", error="Na daný email už je nastavená notifikácia.")
                else:
                    h = hashlib.blake2b(key=current_app.config["APP_SECRET"].encode(), digest_size=16)
                    h.update(frm.email.data.encode())
                    secret = h.digest()
                    with transaction() as t:
                        subscription = GroupSubscription(frm.email.data, None, None, secret, datetime.now(), EligibilityGroup.query.all())
                        t.add(subscription)
                    email_confirmation.delay(subscription.email, hexlify(subscription.secret).decode(), "group")
                    return render_template("confirmation_sent.jinja2", email=subscription.email)
            if frm.push_sub.data:
                # PUSH subscription
                try:
                    sub_data = json.loads(frm.push_sub.data)
                    if not isinstance(sub_data, dict) or "endpoint" not in sub_data:
                        raise ValueError
                except Exception:
                    abort(400)
                endpoint_exists = GroupSubscription.query.filter_by(push_sub_endpoint=sub_data["endpoint"]).first() is not None
                if endpoint_exists:
                    return render_template("ok.html.jinja2", msg="PUSH notifikácie už máte nastavené.")
                else:
                    h = hashlib.blake2b(key=current_app.config["APP_SECRET"].encode(), digest_size=16)
                    h.update(sub_data["endpoint"].encode())
                    secret = h.digest()
                    with transaction() as t:
                        subscription = GroupSubscription(None, json.dumps(sub_data), sub_data["endpoint"], secret, datetime.now(), EligibilityGroup.query.all())
                        t.add(subscription)
                    try:
                        webpush(subscription_info=sub_data,
                                data=json.dumps({"action": "confirm",
                                                 "endpoint": url_for(".group_confirm", secret=hexlify(secret).decode(),
                                                                     push=1)}),
                                vapid_private_key=privkey,
                                vapid_claims=claims)
                    except WebPushException:
                        return render_template("error.html.jinja2", error="Odber notifikácii sa nepodarilo potvrdiť.")
                    return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")
        else:
            abort(400)


@main.route("/groups/unsubscribe/<string(length=32):secret>", methods=["GET", "POST"])
def group_unsubscribe(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    subscription = GroupSubscription.query.filter_by(secret=secret_bytes).first_or_404()
    with transaction() as t:
        t.delete(subscription)
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol úspešne zrušený a Váše osobné údaje (email) boli odstránené.")


@main.route("/groups/confirm/<string(length=32):secret>")
def group_confirm(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    subscription = GroupSubscription.query.filter_by(secret=secret_bytes).first_or_404()
    with transaction():
        subscription.status = Status.CONFIRMED
    if "push" in request.args:
        return jsonify({"msg": "Odber notifikácii bol potvrdený."})
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")


@main.route("/spots/subscribe", methods=["GET", "POST"])
@hcaptcha_required("push_sub")
def spot_subscribe():
    frm = SpotSubscriptionForm()

    cities = VaccinationCity.query.options(joinedload(VaccinationCity.places)).order_by(VaccinationCity.name).all()
    cities.sort(key=lambda city: locale.strxfrm(city.name))
    cities_map = {city.id: city for city in cities}
    cities_id = list(cities_map.items())
    frm.cities.choices = cities_id

    if request.method == "GET" or not frm.validate_on_submit():
        places = VaccinationPlace.query.options(joinedload(VaccinationPlace.days)).filter_by(online=True).all()
        places.sort(key=lambda place: locale.strxfrm(place.city.name))
        dates = list(map(attrgetter("date"), places[0].days))
        dates.sort()

        last_stats = VaccinationStats.query.order_by(VaccinationStats.id.desc()).first()
        return render_template("subscribe_spot.jinja2", form=frm, places=places, dates=dates, last_stats=last_stats)
    else:
        if frm.validate_on_submit():
            if frm.email.data:
                # Email subscription
                email_exists = SpotSubscription.query.filter_by(email=frm.email.data).first() is not None
                if email_exists:
                    return render_template("error.html.jinja2", error="Na daný email už je nastavená notifikácia.")
                else:
                    selected_cities = list(map(lambda city_id: cities_map[city_id], frm.cities.data))
                    h = hashlib.blake2b(key=current_app.config["APP_SECRET"].encode(), digest_size=16)
                    h.update(frm.email.data.encode())
                    secret = h.digest()
                    with transaction() as t:
                        subscription = SpotSubscription(frm.email.data, None, None, secret, datetime.now(), selected_cities, [])
                        t.add(subscription)
                    email_confirmation.delay(frm.email.data, hexlify(secret).decode(), "spot")
                    return render_template("confirmation_sent.jinja2", email=frm.email.data)
            if frm.push_sub.data:
                # PUSH subscription
                try:
                    sub_data = json.loads(frm.push_sub.data)
                    if not isinstance(sub_data, dict) or "endpoint" not in sub_data:
                        raise ValueError
                except Exception:
                    abort(400)
                endpoint_exists = SpotSubscription.query.filter_by(push_sub_endpoint=sub_data["endpoint"]).first() is not None
                if endpoint_exists:
                    return render_template("ok.html.jinja2", msg="PUSH notifikácie už máte nastavené.")
                else:
                    selected_cities = list(map(lambda city_id: cities_map[city_id], frm.cities.data))
                    h = hashlib.blake2b(key=current_app.config["APP_SECRET"].encode(), digest_size=16)
                    h.update(sub_data["endpoint"].encode())
                    secret = h.digest()
                    with transaction() as t:
                        subscription = SpotSubscription(None, json.dumps(sub_data), sub_data["endpoint"], secret, datetime.now(), selected_cities, [])
                        t.add(subscription)
                    try:
                        webpush(subscription_info=sub_data,
                                data=json.dumps({"action": "confirm",
                                                 "endpoint": url_for(".spot_confirm", secret=hexlify(secret).decode(), push=1)}),
                                vapid_private_key=privkey,
                                vapid_claims=claims)
                    except WebPushException:
                        return render_template("error.html.jinja2", error="Odber notifikácii sa nepodarilo potvrdiť.")
                    return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")
        else:
            abort(400)


@main.route("/spots/unsubscribe/<string(length=32):secret>", methods=["GET", "POST"])
def spot_unsubscribe(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    subscription = SpotSubscription.query.filter_by(secret=secret_bytes).first_or_404()
    with transaction() as t:
        t.delete(subscription)
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol úspešne zrušený a Váše osobné údaje (email) boli odstránené.")


@main.route("/spots/confirm/<string(length=32):secret>")
def spot_confirm(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    subscription = SpotSubscription.query.filter_by(secret=secret_bytes).first_or_404()
    with transaction():
        subscription.status = Status.CONFIRMED
    if "push" in request.args:
        return jsonify({"msg": "Odber notifikácii bol potvrdený."})
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")


@main.route("/both/unsubscribe/<string(length=32):secret>", methods=["GET", "POST"])
def both_unsubscribe(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    spot_subscription = SpotSubscription.query.filter_by(secret=secret_bytes).first()
    group_subscription = GroupSubscription.query.filter_by(secret=secret_bytes).first()
    if spot_subscription is not None or group_subscription is not None:
        with transaction() as t:
            if spot_subscription is not None:
                t.delete(spot_subscription)
            if group_subscription is not None:
                t.delete(group_subscription)
        return render_template("ok.html.jinja2",
                               msg="Odber notifikácii bol úspešne zrušený a Váše osobné údaje (email) boli odstránené.")
    else:
        abort(404)


@main.route("/both/confirm/<string(length=32):secret>")
def both_confirm(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    spot_subscription = SpotSubscription.query.filter_by(secret=secret_bytes).first()
    group_subscription = GroupSubscription.query.filter_by(secret=secret_bytes).first()
    if spot_subscription is not None or group_subscription is not None:
        with transaction():
            if spot_subscription is not None:
                spot_subscription.status = Status.CONFIRMED
            if group_subscription is not None:
                group_subscription.status = Status.CONFIRMED
        return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")
    else:
        abort(404)


@main.route("/sw.js")
@sentry_untraced
def service_worker():
    return main.send_static_file("sw.js")


@main.route("/pubkey")
@sentry_untraced
def vapid_pubkey():
    return pubkey
