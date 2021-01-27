#!/usr/bin/env python3
import requests
import json

VACPOINTS_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_driveins_vacc"

if __name__ == "__main__":
    r = requests.get(VACPOINTS_URL)
    payload = r.json()["payload"]
    for place in payload:
        print(place["id"], place["title"])
    with open(f"places.json", "w") as places:
        json.dump(payload, places, indent=2, ensure_ascii=False)
