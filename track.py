#!/usr/bin/env python3
import json
import time
import os

import requests
import click
from twilio.rest import Client

QUERY_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/validate_drivein_times_vacc"


@click.command()
@click.option("-n", "--number", help="Phone number(s) to send alerts to.", multiple=True)
@click.option("-p", "--place", help="IDs of place(s) to alert to.", multiple=True)
@click.option("-c", "--city", help="Cities of place(s) to alert to.", multiple=True)
@click.option("-f", "--frequency", help="Frequency of querying in minutes.", type=click.INT, default=5)
@click.option("--found-frequency", help="Frequency of notifications if free places are found (in minutes).", type=click.INT, default=60)
def main(number, place, city, frequency, found_frequency):
    account_sid = os.environ["TWILIO_SID"]
    auth_token = os.environ["TWILIO_TOKEN"]
    msg_service_sid = os.environ["TWILIO_MSG_SERV_SID"]

    with open("places.json") as f:
        all_places = json.load(f)
    places = [aplace for aplace in all_places if aplace["id"] in place or aplace["city"] in city]
    click.echo(f"[*] Will track places [*]")
    for aplace in places:
        click.echo(f" * {aplace['title']} - {aplace['city']} ({aplace['id']})")
    click.echo(f"[*] Will message numbers [*]")
    for anumber in number:
        click.echo(f" * {anumber}")

    client = Client(account_sid, auth_token)

    while True:
        click.echo("[ ] Querying .....")
        free = {aplace["city"]: 0 for aplace in places}
        for aplace in places:
            r = requests.post(QUERY_URL, json={"drivein_id": str(aplace["id"])})
            js = r.json()
            for line in js["payload"]:
                if line["free_capacity"] != "0" and line["is_closed"] != "1":
                    try:
                        amount = int(line["free_capacity"])
                    except Exception:
                        # Handle possibly weird number format by NCZI gracefully and actually notice anything different from 0.
                        amount = 1
                    free[aplace["city"]] += amount
        if any(free.values()):
            click.echo("[*] Found places [*]")
            msg_body = "Voľné miesta na očkovanie: " + ", ".join(f"{name} ({amount})" for name, amount in free.items() if amount != 0)
            click.echo(msg_body)
            for anumber in number:
                click.echo(f"[*] Messaging {anumber} [*]")
                msg = client.messages.create(
                    to=anumber,
                    messaging_service_sid=msg_service_sid,
                    body=msg_body
                )
                click.echo(f" * Status: {msg.status}, {msg.error_message}")
            time.sleep(60 * found_frequency)
        else:
            click.echo("[ ] Found nothing :(")
            time.sleep(60 * frequency)


if __name__ == "__main__":
    main()
