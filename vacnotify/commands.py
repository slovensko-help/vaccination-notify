from binascii import hexlify
from datetime import timedelta, datetime

import sentry_sdk
from sqlalchemy import and_
from functools import wraps

import click
import re

from vacnotify import app
from vacnotify.tasks.email import email_confirmation
from vacnotify.tasks.query import run, compute_subscription_stats
from vacnotify.models import SpotSubscription, GroupSubscription, Status


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
@click.option("-t", "--type", "sub_type", type=click.Choice(("spot", "group", "both")), help="Which subscription type to send confirmation to.", default="both")
@click.option("-n", "--dry-run", "dry_run", is_flag=True, help="Do not actually send anything.")
@click.option("-o", "--older", "older_than", type=str, metavar="<timedelta>", help="Only send to subscription created more than <older_than> time units ago.")
@click.argument("emails", nargs=-1, type=str)
def resend_confirmation(sub_type, dry_run, older_than, emails):
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
        to_send.extend((subscription.email, hexlify(subscription.secret).decode(), "spot") for subscription in spot_subs)
        click.echo(f"Found {len(spot_subs)} unconfirmed spot subscriptions.")
    # Get the group subs
    if sub_type in ("group", "both"):
        if older_than:
            query = GroupSubscription.query.filter(and_(GroupSubscription.status == Status.UNCONFIRMED, GroupSubscription.created_at < now - older_than))
        else:
            query = GroupSubscription.query.filter(GroupSubscription.status == Status.UNCONFIRMED)
        group_subs = query.all()
        to_send.extend((subscription.email, hexlify(subscription.secret).decode(), "group") for subscription in group_subs)
        click.echo(f"Found {len(group_subs)} unconfirmed group subscriptions.")
    # Filter emails
    to_send = list(filter(lambda entry: not emails or entry[0] in emails, to_send))
    # Map to (email, secret) to resend only one "both" type confirmation where we can
    email_secret_map = {}
    for email, secret, send_type in to_send:
        if (email, secret) in email_secret_map:
            email_secret_map[(email, secret)] = "both"
        else:
            email_secret_map[(email, secret)] = send_type
    # Send stuff
    for email_secret, send_type in email_secret_map.items():
        email, secret = email_secret
        if dry_run:
            click.echo(f"Would send {send_type} confirmation email to {email}.")
        else:
            click.echo(f"Sending {send_type} confirmation email to {email}.")
            email_confirmation.delay(email, secret, send_type)


@app.cli.command("trigger-query", help="Manually trigger query of API server (also sends notifications).")
@command_transaction
def trigger_query():
    run.delay()
