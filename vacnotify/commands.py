from binascii import hexlify
from datetime import timedelta, datetime
from sqlalchemy import and_

import click
import re

from vacnotify import app
from vacnotify.models import SpotSubscription, GroupSubscription, Status
from vacnotify.tasks import email_confirmation, run


@app.cli.command("count-subscriptions", help="Count the subscriptions and users in the DB.")
def count_users():
    confirmed_spot_subs = SpotSubscription.query.filter(SpotSubscription.status == Status.CONFIRMED).count()
    unconfirmed_spot_subs = SpotSubscription.query.filter(SpotSubscription.status == Status.UNCONFIRMED).count()
    confirmed_group_subs = GroupSubscription.query.filter(GroupSubscription.status == Status.CONFIRMED).count()
    unconfirmed_group_subs = GroupSubscription.query.filter(GroupSubscription.status == Status.UNCONFIRMED).count()
    emails = set()
    emails.update(SpotSubscription.query.with_entities(SpotSubscription.email).all())
    emails.update(GroupSubscription.query.with_entities(GroupSubscription.email).all())
    click.echo(f"Unique emails: {len(emails)}")
    click.echo(f"Spot subscriptions:")
    click.echo(f" - Confirmed: {confirmed_spot_subs}")
    click.echo(f" - Unconfirmed: {unconfirmed_spot_subs}")
    click.echo(f"Group subscriptions:")
    click.echo(f" - Confirmed: {confirmed_group_subs}")
    click.echo(f" - Unconfirmed: {unconfirmed_group_subs}")


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
def trigger_query():
    run.s()
