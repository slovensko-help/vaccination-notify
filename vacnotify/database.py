from contextlib import contextmanager

from vacnotify import db


@contextmanager
def transaction():
    try:
        yield db.session
    except:
        db.session.rollback()
        raise
    else:
        db.session.commit()
