import json
from binascii import hexlify
from datetime import timedelta, datetime

import sentry_sdk
from flask import url_for
from flask_mail import Message
from sqlalchemy import and_
from functools import wraps
from itertools import zip_longest

import click
import re

from sqlalchemy.orm import joinedload
from tqdm import tqdm

from vacnotify import app, mail
from vacnotify.tasks.email import email_confirmation
from vacnotify.tasks.push import push_confirmation, push_notification
from vacnotify.tasks.query import run, compute_subscription_stats
from vacnotify.models import SpotSubscription, GroupSubscription, Status, SubscriptionType



def command_transaction(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with sentry_sdk.start_transaction(op="command", name=".".join((__name__, func.__name__))):
            return func(*args, **kwargs)
    return wrapper


@app.cli.command("count-subscriptions", help="Count the subscriptions and users in the DB.")
@command_transaction
def count_users():
    stats = compute_subscription_stats()
    total_spot_subs = stats["spot_subs_confirmed"] + stats["spot_subs_unconfirmed"]
    click.echo(f"Unique emails: {stats['unique_emails']}")
    click.echo(f"Shared emails: {stats['shared_emails']}")
    click.echo(f"Unique PUSH subscriptions: {stats['unique_push_subs']}")
    click.echo(f"Shared PUSH subscriptions: {stats['shared_push_subs']}")
    click.echo(f"Spot subscriptions: top(id) = {stats['spot_subs_top_id']}, total = {total_spot_subs}")
    click.echo(f" - Confirmed: {stats['spot_subs_confirmed']}")
    click.echo(f" - Unconfirmed: {stats['spot_subs_unconfirmed']}")
    if total_spot_subs != 0:
        click.echo(f" - Ratio: {stats['spot_subs_confirmed'] / total_spot_subs}")
    total_group_subs = stats["group_subs_confirmed"] + stats["group_subs_unconfirmed"]
    click.echo(f"Group subscriptions: top(id) = {stats['group_subs_top_id']}, total = {total_group_subs}")
    click.echo(f" - Confirmed: {stats['group_subs_confirmed']}")
    click.echo(f" - Unconfirmed: {stats['group_subs_unconfirmed']}")
    if total_group_subs != 0:
        click.echo(f" - Ratio: {stats['group_subs_confirmed'] / total_group_subs}")


timedelta_re = re.compile(r'((?P<days>\d+?)d)?((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')


def parse_time(time_str):
    if time_str is None:
        return None
    parts = timedelta_re.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)


@app.cli.command("resend-confirmation", help="Resend confirmation emails to unconfirmed addresses.")
@command_transaction
@click.option("-m", "--method", "method", type=click.Choice(("email", "push", "both")), help="Which subscription method to send to.", default="both")
@click.option("-t", "--type", "sub_type", type=click.Choice(("spot", "group", "both")), help="Which subscription type to send confirmation to.", default="both")
@click.option("-n", "--dry-run", "dry_run", is_flag=True, help="Do not actually send anything.")
@click.option("-o", "--older", "older_than", type=str, metavar="<timedelta>", help="Only send to subscription created more than <older_than> time units ago.")
@click.argument("ids", nargs=-1, type=int)
def resend_confirmation(method, sub_type, dry_run, older_than, ids):
    # TODO: make this also send PUSHes
    older_than = parse_time(older_than)
    now = datetime.now()
    to_send = []
    # Get the spot subs
    if sub_type in ("spot", "both"):
        if older_than:
            query = SpotSubscription.query.filter(and_(SpotSubscription.status == Status.UNCONFIRMED, SpotSubscription.created_at < now - older_than))
        else:
            query = SpotSubscription.query.filter(SpotSubscription.status == Status.UNCONFIRMED)
        spot_subs = query.all()
        to_send.extend(spot_subs)
        click.echo(f"Found {len(spot_subs)} unconfirmed spot subscriptions.")
    # Get the group subs
    if sub_type in ("group", "both"):
        if older_than:
            query = GroupSubscription.query.filter(and_(GroupSubscription.status == Status.UNCONFIRMED, GroupSubscription.created_at < now - older_than))
        else:
            query = GroupSubscription.query.filter(GroupSubscription.status == Status.UNCONFIRMED)
        group_subs = query.all()
        to_send.extend(group_subs)
        click.echo(f"Found {len(group_subs)} unconfirmed group subscriptions.")
    # Filter emails
    to_send = list(filter(lambda sub: not ids or sub.id in ids, to_send))
    # Map to secret to resend only one "both" type confirmation where we can
    secret_map = {}
    for subscription in to_send:
        if subscription.secret in secret_map:
            secret_map[subscription.secret].append(subscription)
        else:
            secret_map[subscription.secret] = [subscription]
    for secret, subs in secret_map.items():
        if len(subs) == 1:
            sub_type = "spot" if isinstance(subs[0], SpotSubscription) else "group"
        else:
            sub_type = "both"

        if subs[0].subscription_type == SubscriptionType.Email:
            if dry_run:
                click.echo(f"Would send {sub_type} confirmation email to {subs[0].email}.")
            elif method in ("email", "both"):
                click.echo(f"Sending {sub_type} confirmation email to {subs[0].email}.")
                email_confirmation.delay(subs[0].email, hexlify(secret).decode(), sub_type)
        else:
            if dry_run:
                click.echo(f"Would send {sub_type} confirmation PUSH to [{subs[0].id}].")
            elif method in ("push", "both"):
                click.echo(f"Sending {sub_type} confirmation PUSH to [{subs[0].id}].")
                push_confirmation.delay(json.loads(subs[0].push_sub), hexlify(secret).decode(), sub_type)


@app.cli.command("trigger-query", help="Manually trigger query of API server (also sends notifications).")
@command_transaction
def trigger_query():
    run.delay()


@app.cli.command("find", help="Find a subscription by email.")
@command_transaction
@click.argument("email")
def find_email(email):
    spot_subs = SpotSubscription.query.options(joinedload(SpotSubscription.cities), joinedload(SpotSubscription.known_cities)).filter_by(email=email).all()
    group_subs = GroupSubscription.query.options(joinedload(GroupSubscription.known_groups)).filter_by(email=email).all()
    for sub in spot_subs:
        print(sub)
        for city in sub.cities:
            print(f"\t- {city.name} {'*' if city in sub.known_cities else ''}")
    for sub in group_subs:
        print(sub)
        print(f"\t {sub.known_groups}")


@app.cli.command("send-email", help="Send email using the app's sender.")
@command_transaction
@click.option("-s", "--subject", required=True, help="The subject of the email.")
@click.option("-b", "--body", help="The content of the email body.", type=click.File())
@click.option("-c", "--content-type", "content_type", help="The type of the body.", type=click.Choice(("html", "text")), default="text")
@click.option("-t", "--type", "sub_type", type=click.Choice(("spot", "group", "both")), help="Which subscription type to send confirmation to.", default="both")
@click.option("--status", type=click.Choice(("CONFIRMED", "UNCONFIRMED")), help="Status of subs to send to.", default="CONFIRMED")
@click.option("--batch", type=int, help="Amount of emails to send per connection.", default=1)
@click.option("--dry-run", "dry_run", is_flag=True, help="Do not actually send anything.")
def send_email(subject, body, content_type, sub_type, status, batch, dry_run):
    def grouper(n, iterable, padvalue=None):
        return zip_longest(*[iter(iterable)] * n, fillvalue=padvalue)

    status = Status.CONFIRMED if status == "CONFIRMED" else Status.UNCONFIRMED

    to_send = set()
    if sub_type in ("spot", "both"):
        subs = SpotSubscription.query.filter(SpotSubscription.status == status, SpotSubscription.email.isnot(None)).all()
        to_send.update([(sub.email, sub.secret, "spot") for sub in subs])
    if sub_type in ("group", "both"):
        subs = GroupSubscription.query.filter(GroupSubscription.status == status, GroupSubscription.email.isnot(None)).all()
        to_send.update([(sub.email, sub.secret, "group") for sub in subs])
    click.echo(f"[ ] Sending to {len(to_send)} emails. Batching to {batch}. {'Dry-run' if dry_run else ''}")
    click.confirm("Continue?", abort=True)

    joined_send = {}
    for email, secret, stype in to_send:
        if secret in joined_send:
            joined_send[secret] = (email, "both")
        else:
            joined_send[secret] = (email, stype)

    content = body.read()

    for entry_batch in tqdm(grouper(batch, joined_send.items())):
        click.echo("[ ] Connecting to server.")
        with mail.connect() as conn:
            for entry in entry_batch:
                if entry is None:
                    continue
                secret, pair = entry
                email, stype = pair
                unsub_link = url_for(f"main.{stype}_unsubscribe", secret=hexlify(secret).decode())
                if dry_run:
                    click.echo(f"[ ] Would send email to {email}.")
                    continue
                msg = Message(subject, recipients=[email])
                if content_type == "html":
                    msg.html = content + f"""\n<p>Ak už nechcete dostávať notifikačné emaily, kliknite na link nižšie alebo ho skopírujte do svojho webového
                                                  prehliadača. Po odhlásení už notifikácie dostávať nebudete a Vaše osobné údaje (email) budú vymazané.
                                               </p>
                                               <a href="{ unsub_link }" target="_blank">{ unsub_link }</a>"""
                if content_type == "text":
                    msg.body = content + f"""\nAk už nechcete dostávať notifikačné emaily, kliknite na link nižšie alebo ho skopírujte do svojho webového prehliadača. Po odhlásení už notifikácie dostávať nebudete a Vaše osobné údaje (email) budú vymazané.\n{ unsub_link }"""
                conn.send(msg)


@app.cli.command("send-push")
@click.option("-b", "--body", help="The content of the body.", type=click.File())
@click.option("-t", "--type", "sub_type", type=click.Choice(("spot", "group", "both")), help="Which subscription type to send confirmation to.", default="both")
@click.option("--status", type=click.Choice(("CONFIRMED", "UNCONFIRMED")), help="Status of subs to send to.", default="CONFIRMED")
@click.option("--dry-run", "dry_run", is_flag=True, help="Do not actually send anything.")
def send_push(body, sub_type, status, dry_run):
    status = Status.CONFIRMED if status == "CONFIRMED" else Status.UNCONFIRMED
    to_send = set()
    if sub_type in ("spot", "both"):
        subs = SpotSubscription.query.filter(SpotSubscription.status == status, SpotSubscription.push_sub_endpoint.isnot(None)).all()
        to_send.update([sub.push_sub for sub in subs])
    if sub_type in ("group", "both"):
        subs = GroupSubscription.query.filter(GroupSubscription.status == status, GroupSubscription.push_sub_endpoint.isnot(None)).all()
        to_send.update([sub.push_sub for sub in subs])
    click.echo(f"[ ] Sending to {len(to_send)} subscriptions. {'Dry-run' if dry_run else ''}")
    click.confirm("Continue?", abort=True)

    content = body.read()

    for push_sub in tqdm(to_send):
        if dry_run:
            click.echo(f"[ ] Would send PUSH.")
            continue
        sub_info = json.loads(push_sub)
        push_notification(sub_info, content)
