import datetime
import pytz

_eastern = pytz.timezone("US/Eastern")


def today():
    return datetime.datetime.now(_eastern)


def convert_to_utc(dt):
    return dt.astimezone(pytz.utc)


def convert_to_est(dt):
    return dt.astimezone(_eastern)


def localize_to_et(dt):
    return _eastern.localize(dt)


def to_day(dt: datetime.datetime):
    return datetime.datetime(dt.year, dt.month, dt.day, tzinfo=_eastern)
