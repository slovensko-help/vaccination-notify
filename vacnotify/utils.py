from datetime import datetime
from flask.json import JSONEncoder
from typing import Any


class CustomEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.strftime("%Y-%m-%dT%H:%M")
        elif hasattr(o, "__json__") and callable(getattr(o, "__json__")):
            return o.__json__()
        else:
            return JSONEncoder.default(self, o)
