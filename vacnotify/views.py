import hashlib
import json
import locale
import requests
from binascii import unhexlify, hexlify
from datetime import datetime, timedelta
from json import JSONDecodeError
from operator import attrgetter, itemgetter

from flask import render_template, request, abort, current_app, jsonify, url_for, g
from sqlalchemy.orm import joinedload
from pywebpush import webpush, WebPushException

from vacnotify import vapid_pubkey as pubkey, vapid_privkey as privkey, vapid_claims as claims, cache
from vacnotify.blueprint import main
from vacnotify.database import transaction
from vacnotify.models import EligibilityGroup, VaccinationPlace, GroupSubscription, Status, SpotSubscription, \
    VaccinationStats, VaccinationCity, SubscriptionStats, UserFeedback
from vacnotify.forms import GroupSubscriptionForm, SpotSubscriptionForm, UnsubscriptionForm
from vacnotify.tasks.email import email_confirmation
from vacnotify.utils import hcaptcha_required, sentry_untraced, embedded, embeddable


@main.route("/")
@embedded
def index():
    return render_template("index.html.jinja2")


@main.route("/privacy")
@embedded
def privacy():
    return render_template("privacy_policy.html.jinja2")


@main.route("/faq")
@embedded
def faq():
    return render_template("faq.html.jinja2")


@cache.cached(1800, "substitutes", response_filter=lambda resp: resp is not None)
def get_substitutes():
    def get_data(s, url):
        resp = s.get(url)
        if not resp:
            return None
        try:
            return resp.json()
        except JSONDecodeError:
            return None
    with requests.session() as s:
        if not (subs := get_data(s, "https://data.korona.gov.sk/api/vaccination/contacts")) or not subs["success"]:
            return None
        if not (hospitals := get_data(s, "https://data.korona.gov.sk/api/hospitals")):
            return None
        if not (cities := get_data(s, "https://data.korona.gov.sk/api/cities")):
            return None
        if not (districts := get_data(s, "https://data.korona.gov.sk/api/districts")):
            return None
        if not (regions := get_data(s, "https://data.korona.gov.sk/api/regions")):
            return None
    for region in regions:
        region_district_ids = [district["id"] for district in districts if district["region_id"] == region["id"]]
        region_city_ids = [city["id"] for city in cities if city["district_id"] in region_district_ids]
        region_hospitals = [hospital for hospital in hospitals if hospital["city_id"] in region_city_ids]
        region_hospitals.sort(key=itemgetter("title"))
        for hospital in region_hospitals:
            for sub in subs["page"]:
                if sub["hospital_id"] == hospital["id"]:
                    hospital["contacts"] = sub
                    break
            else:
                hospital["contacts"] = None
        region["hospitals"] = region_hospitals
    regions.sort(key=itemgetter("title"))
    return regions


@main.route("/substitutes")
@embedded
def substitute_lists():
    return render_template("substitute_lists.html.jinja2", substitutes=get_substitutes())


@main.route("/stats")
@embedded
def stats():
    vaccination_stats = VaccinationStats.query.filter(VaccinationStats.datetime > (datetime.now() - timedelta(days=7))).order_by(VaccinationStats.id.desc()).all()
    subscription_stats = SubscriptionStats.query.filter(SubscriptionStats.datetime > (datetime.now() - timedelta(days=7))).order_by(SubscriptionStats.id.desc()).all()

    return render_template("stats.html.jinja2", vaccination_stats=vaccination_stats, subscription_stats=subscription_stats,
                           current_vstats=vaccination_stats[0], current_sstats=subscription_stats[0])


@main.route("/groups/subscribe", methods=["GET", "POST"])
@hcaptcha_required("push_sub")
@embedded
def group_subscribe():
    frm = GroupSubscriptionForm()
    if request.method == "GET" or not frm.validate_on_submit():
        last_stats = VaccinationStats.query.order_by(VaccinationStats.id.desc()).first()
        return render_template("subscribe_group.jinja2", form=frm, groups=EligibilityGroup.query.all(), last_stats=last_stats)
    else:
        if frm.validate_on_submit():
            if frm.email.data:
                # Email subscription
                if not current_app.config["EMAIL_ENABLED"]:
                    return render_template("error.html.jinja2", error="Emailové notifikácie nie sú v prevádzke."), 400
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
                if not current_app.config["PUSH_ENABLED"]:
                    return render_template("error.html.jinja2", error="PUSH notifikácie nie sú v prevádzke."), 400
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
@embeddable
def group_unsubscribe(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    subscription = GroupSubscription.query.filter_by(secret=secret_bytes).first()
    if not subscription:
        return render_template("error.html.jinja2", error="Odber notifikácii sa nenašiel, buď neexistuje alebo bol už zrušený."), 404
    with transaction() as t:
        t.delete(subscription)
        fb = UserFeedback(secret_bytes)
        t.add(fb)
    form = UnsubscriptionForm()
    form.secret.data = secret
    form.id.data = str(fb.id)
    if "push" in request.args:
        msg = "Odber notifikácii bol úspešne zrušený."
    else:
        msg = "Odber notifikácii bol úspešne zrušený a Vaše osobné údaje (email) boli odstránené."
    return render_template("unsubscribe.html.jinja2", msg=msg, form=form)


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
        return jsonify({"msg": "Odber notifikácii bol potvrdený.",
                        "type": "group",
                        "unsubscribe": url_for("main.group_unsubscribe", secret=secret, _external=True)})
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")


@main.route("/spots/subscribe", methods=["GET", "POST"])
@hcaptcha_required("push_sub")
@embedded
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
        any_free = any(place.free > 0 for place in places)

        last_stats = VaccinationStats.query.order_by(VaccinationStats.id.desc()).first()
        return render_template("subscribe_spot.jinja2", form=frm, places=places, dates=dates, last_stats=last_stats, any_free=any_free)
    else:
        if frm.validate_on_submit():
            if frm.email.data:
                # Email subscription
                if not current_app.config["EMAIL_ENABLED"]:
                    return render_template("error.html.jinja2", error="Emailové notifikácie nie sú v prevádzke."), 400
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
                if not current_app.config["PUSH_ENABLED"]:
                    return render_template("error.html.jinja2", error="PUSH notifikácie nie sú v prevádzke."), 400
                try:
                    sub_data = json.loads(frm.push_sub.data)
                    if not isinstance(sub_data, dict) or "endpoint" not in sub_data:
                        raise ValueError
                except Exception:
                    abort(400)
                existing_subscription = SpotSubscription.query.filter_by(push_sub_endpoint=sub_data["endpoint"]).first()
                selected_cities = list(map(lambda city_id: cities_map[city_id], frm.cities.data))
                if existing_subscription is not None:
                    with transaction():
                        existing_subscription.cities = selected_cities
                        existing_subscription.known_cities = list(set(existing_subscription.known_cities).intersection(selected_cities))
                    try:
                        webpush(subscription_info=sub_data,
                                data=json.dumps({"action": "confirm",
                                                 "endpoint": url_for(".spot_confirm", secret=hexlify(existing_subscription.secret).decode(), push=1)}),
                                vapid_private_key=privkey,
                                vapid_claims=claims)
                    except WebPushException:
                        return render_template("error.html.jinja2", error="Odber notifikácii sa nepodarilo aktualizovať.")
                    return render_template("ok.html.jinja2", msg="Vaše nastavenie PUSH notifikácii bolo aktualizované.")
                else:
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
@embeddable
def spot_unsubscribe(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    subscription = SpotSubscription.query.filter_by(secret=secret_bytes).first()
    if not subscription:
        return render_template("error.html.jinja2", error="Odber notifikácii sa nenašiel, buď neexistuje alebo bol už zrušený."), 404
    with transaction() as t:
        t.delete(subscription)
        fb = UserFeedback(secret_bytes)
        t.add(fb)
    form = UnsubscriptionForm()
    form.secret.data = secret
    form.id.data = str(fb.id)
    if "push" in request.args:
        msg = "Odber notifikácii bol úspešne zrušený."
    else:
        msg = "Odber notifikácii bol úspešne zrušený a Vaše osobné údaje (email) boli odstránené."
    return render_template("unsubscribe.html.jinja2", msg=msg, form=form)


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
        return jsonify({"msg": "Odber notifikácii bol potvrdený.",
                        "cities": [{"id": city.id, "name": city.name} for city in subscription.cities],
                        "type": "spot",
                        "unsubscribe": url_for("main.spot_unsubscribe", secret=secret, _external=True)})
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")


@main.route("/both/unsubscribe/<string(length=32):secret>", methods=["GET", "POST"])
@embeddable
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
        if "push" in request.args:
            msg = "Odber notifikácii bol úspešne zrušený."
        else:
            msg = "Odber notifikácii bol úspešne zrušený a Vaše osobné údaje (email) boli odstránené."
        return render_template("ok.html.jinja2", msg=msg)
    else:
        return render_template("error.html.jinja2", error="Odber notifikácii sa nenašiel, buď neexistuje alebo bol už zrušený."), 404


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
        if "push" in request.args:
            return jsonify({"msg": "Odber notifikácii bol potvrdený.",
                            "type": "both",
                            "unsubscribe": url_for("main.both_unsubscribe", secret=secret, _external=True)})
        return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")
    else:
        abort(404)


@main.route("/feedback", methods=["POST"])
@embeddable
def feedback():
    form = UnsubscriptionForm()
    if form.validate_on_submit():
        try:
            secret = unhexlify(form.secret.data)
        except ValueError:
            abort(400)
        user_feedback = UserFeedback.query.filter(UserFeedback.id == int(form.id.data), UserFeedback.secret == secret).first()
        if not user_feedback:
            abort(400)
        if user_feedback.given:
            return render_template("error.html.jinja2", error="Spätnú väzbu je možné odoslať len raz.")
        with transaction():
            user_feedback.give(form.reasons.data, form.feedback.data)
        return render_template("ok.html.jinja2", msg="Spätná väzba bola úspešne odoslaná. Ďakujeme.")
    else:
        abort(400)


@main.route("/sw.js")
@sentry_untraced
def service_worker():
    return main.send_static_file("sw.js")


@main.route("/pubkey")
@sentry_untraced
def vapid_pubkey():
    return pubkey


@main.route("/embed")
def embed():
    url = request.args.get("url", url_for(".index"))
    return render_template("embed.html.jinja2", url=url)
