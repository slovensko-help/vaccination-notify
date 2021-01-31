from binascii import unhexlify, hexlify
from datetime import datetime, timedelta
from operator import attrgetter

from flask import render_template, request, abort, current_app
from vacnotify.blueprint import main
from vacnotify.database import transaction
from vacnotify.models import EligibilityGroup, VaccinationPlace, GroupSubscription, Status, SpotSubscription, \
    VaccinationStats
from vacnotify.forms import GroupSubscriptionForm, SpotSubscriptionForm
from vacnotify.tasks import email_confirmation
from vacnotify.utils import hcaptcha_required


@main.route("/")
def index():
    groups = EligibilityGroup.query.all()
    places = VaccinationPlace.query.order_by(VaccinationPlace.city).all()
    dates = list(map(attrgetter("date"), places[0].days))

    stats = VaccinationStats.query.filter(VaccinationStats.datetime > (datetime.now() - timedelta(days=1))).order_by(VaccinationStats.id.desc()).all()
    current_stats = VaccinationStats.query.order_by(VaccinationStats.id.desc()).first()

    return render_template("index.html.jinja2", groups=groups, places=places, dates=dates, stats=stats, current_stats=current_stats)


@main.route("/groups/subscribe", methods=["GET", "POST"])
@hcaptcha_required
def group_subscribe():
    frm = GroupSubscriptionForm()
    if request.method == "GET" or not frm.validate_on_submit():
        return render_template("subscribe_group.jinja2", form=frm, groups=EligibilityGroup.query.all())
    else:
        if frm.validate_on_submit():
            email_exists = GroupSubscription.query.filter_by(email=frm.email.data).first() is not None
            if email_exists:
                return render_template("error.html.jinja2", error="Na daný email už je nastavená notifikácia.")
            else:
                with transaction() as t:
                    subscription = GroupSubscription(frm.email.data, EligibilityGroup.query.all())
                    t.add(subscription)
                email_confirmation.delay(subscription.email, hexlify(subscription.secret).decode(), "group")
                return render_template("ok.html.jinja2",
                                       msg=f"Na email {subscription.email} bol zaslaný potvrdzovací email. Potvrdenie žiadosti o notifikácie kliknutím na link v emaili je potrebné na získavanie notifikacii. "
                                           f"Skontrolujte aj priečinok SPAM do ktorého sa potvrdzovací email mohol dostať. Email prichádza z adresy {current_app.config['MAIL_DEFAULT_SENDER']}.")
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
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol úspešne zrušený.")


@main.route("/groups/confirm/<string(length=32):secret>")
def group_confirm(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    subscription = GroupSubscription.query.filter_by(secret=secret_bytes).first_or_404()
    with transaction():
        subscription.status = Status.CONFIRMED
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")


@main.route("/spots/subscribe", methods=["GET", "POST"])
@hcaptcha_required
def spot_subscribe():
    frm = SpotSubscriptionForm()
    places = VaccinationPlace.query.order_by(VaccinationPlace.city).all()
    dates = list(map(attrgetter("date"), places[0].days))
    cities = set(map(attrgetter("city"), places))
    cities_id = list(map(lambda city: (hash(city), city), sorted(cities)))
    frm.places.choices = cities_id
    if request.method == "GET" or not frm.validate_on_submit():
        return render_template("subscribe_spot.jinja2", form=frm, places=places, dates=dates)
    else:
        if frm.validate_on_submit():
            email_exists = SpotSubscription.query.filter_by(email=frm.email.data).first() is not None
            if email_exists:
                return render_template("error.html.jinja2", error="Na daný email už je nastavená notifikácia.")
            else:
                selected_cities = filter(lambda x: x[0] in frm.places.data, cities_id)
                selected_places = set()
                for _, selected_city in selected_cities:
                    selected_places.update(filter(lambda place: place.city == selected_city, places))
                with transaction() as t:
                    subscription = SpotSubscription(frm.email.data, list(selected_places))
                    t.add(subscription)
                email_confirmation.delay(subscription.email, hexlify(subscription.secret).decode(), "spot")
                return render_template("ok.html.jinja2",
                                       msg=f"Na email {subscription.email} bol zaslaný potvrdzovací email. Potvrdenie žiadosti o notifikácie kliknutím na link v emaili je potrebné na získavanie notifikacii. "
                                           f"Skontrolujte aj priečinok SPAM do ktorého sa potvrdzovací email mohol dostať. Email prichádza z adresy {current_app.config['MAIL_DEFAULT_SENDER']}.")
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
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol úspešne zrušený.")


@main.route("/spots/confirm/<string(length=32):secret>")
def spot_confirm(secret):
    try:
        secret_bytes = unhexlify(secret)
    except Exception:
        abort(404)
    subscription = SpotSubscription.query.filter_by(secret=secret_bytes).first_or_404()
    with transaction():
        subscription.status = Status.CONFIRMED
    return render_template("ok.html.jinja2", msg="Odber notifikácii bol potvrdený.")
