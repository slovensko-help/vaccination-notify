#!/usr/bin/env python3
import requests
import json

GROUPS_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_vaccination_groups"

if __name__ == "__main__":
    r = requests.get(GROUPS_URL)
    payload = r.json()["payload"]
    for group in payload:
        print(group["item_code"], group["item_description_ui"])
    with open(f"groups.json", "w") as groups:
        json.dump(payload, groups, indent=2, ensure_ascii=False)
