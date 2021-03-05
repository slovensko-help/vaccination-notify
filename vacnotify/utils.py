import hashlib
from datetime import datetime

import requests
import sentry_sdk
from flask.json import JSONEncoder
from typing import Any
from functools import wraps
from flask import request, abort, current_app, g


class CustomEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.strftime("%Y-%m-%dT%H:%M")
        elif hasattr(o, "__json__") and callable(getattr(o, "__json__")):
            return o.__json__()
        else:
            return JSONEncoder.default(self, o)


def hcaptcha_required(passthru_arg):
    def hcaptcha_deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.method == "POST":
                if passthru_arg in request.form and request.form[passthru_arg]:
                    return f(*args, **kwargs)
                if "h-captcha-response" not in request.form:
                    abort(403)
                captcha = request.form["h-captcha-response"]
                if not captcha:
                    abort(403)
                captcha_resp = requests.post("https://hcaptcha.com/siteverify",
                                             data={"response": captcha,
                                                   "secret": current_app.config["HCAPTCHA_SECRET_KEY"],
                                                   "ip": request.remote_addr,
                                                   "sitekey": current_app.config["HCAPTCHA_SITEKEY"]})
                captcha_result = captcha_resp.json()
                if not captcha_result["success"]:
                    abort(403)
            return f(*args, **kwargs)
        return wrapper
    return hcaptcha_deco


def sentry_untraced(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with sentry_sdk.configure_scope() as scope:
            if scope.transaction:
                scope.transaction.sampled = False
            return f(*args, **kwargs)
    return wrapper


def remove_pii(*args):
    h = hashlib.blake2b(digest_size=20)
    for arg in args:
        if isinstance(arg, str):
            h.update(arg.encode())
        elif isinstance(arg, bytes):
            h.update(arg)
    return h.hexdigest()


def embedded(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        g.embed = True
        return f(*args, **kwargs)
    return wrapper


def embeddable(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "embed" in request.args:
            g.embed = True
        return f(*args, **kwargs)
    return wrapper
