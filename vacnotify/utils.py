from datetime import datetime

import requests
from flask.json import JSONEncoder
from typing import Any
from functools import wraps
from flask import request, abort, current_app


class CustomEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.strftime("%Y-%m-%dT%H:%M")
        elif hasattr(o, "__json__") and callable(getattr(o, "__json__")):
            return o.__json__()
        else:
            return JSONEncoder.default(self, o)


def hcaptcha_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == "POST":
            if "h-captcha-response" not in request.form:
                abort(403)
            captcha = request.form["h-captcha-response"]
            captcha_resp = requests.post("https://hcaptcha.com/siteverify", data={"response": captcha,
                                                                                  "secret": current_app.config[
                                                                                      "HCAPTCHA_SECRET_KEY"],
                                                                                  "ip": request.remote_addr,
                                                                                  "sitekey": current_app.config["HCAPTCHA_SITEKEY"]})
            captcha_result = captcha_resp.json()
            if not captcha_result["success"]:
                abort(403)
        return f(*args, **kwargs)
    return wrapper
