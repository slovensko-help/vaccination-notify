#!/usr/bin/env python3
import json
import time
import os

import requests
import click
from twilio.rest import Client

GROUPS_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_vaccination_groups"


@click.command()
@click.option("-n", "--number", help="Phone number(s) to send alerts to.", multiple=True)
@click.option("-f", "--frequency", help="Frequency of querying in minutes.", type=click.INT, default=5)
def main(number, frequency):
    account_sid = os.environ["TWILIO_SID"]
    auth_token = os.environ["TWILIO_TOKEN"]
    msg_service_sid = os.environ["TWILIO_MSG_SERV_SID"]

    with open("groups.json") as f:
        previous_groups = json.load(f)
    click.echo("[*] Current groups [*]")
    for group in previous_groups:
        click.echo(f" * {group['item_code']} - {group['item_description_ui']}")
    click.echo("[*] Will message numbers [*]")
    for anumber in number:
        click.echo(f" * {anumber}")

    client = Client(account_sid, auth_token)

    while True:
        click.echo("[ ] Querying .....")
        r = requests.get(GROUPS_URL)
        payload = r.json()["payload"]
        new_groups = []
        for group in payload:
            for old_group in previous_groups:
                if group["item_code"] == old_group["item_code"]:
                    break
            else:
                new_groups.append(group)
        if new_groups:
            click.echo(f"[*] Found new group [*]")
            msg_body = f"Nové skupiny na očkovanie: " + ", ".join(f"{group['item_code']} - {group['item_description_ui']}" for group in new_groups)
            click.echo(msg_body)
            for anumber in number:
                click.echo(f"[*] Messaging {anumber} [*]")
                msg = client.messages.create(
                    to=anumber,
                    messaging_service_sid=msg_service_sid,
                    body=msg_body
                )
                click.echo(f" * Status: {msg.status}, {msg.error_message}")
            break
        else:
            click.echo("[ ] Found nothing :(")
            time.sleep(60 * frequency)


if __name__ == "__main__":
    main()
