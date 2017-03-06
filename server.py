import os
import json
import logging
from datetime import timedelta
from operator import itemgetter
from itertools import groupby
from collections import namedtuple, UserDict

import flask
from arrow import Arrow
import dateutil.tz as dateutil_tz
from arrow import get as get_date
from arrow.parser import ParserError
from flask import request, redirect, url_for, render_template, abort, jsonify

from via_website import get_dates

logging.basicConfig(level=logging.INFO)
app = flask.Flask(__name__)

ONE_DAY = timedelta(days=1)
ONE_HOUR = timedelta(hours=1)
AU_PERTH = dateutil_tz.gettz('Australia/Perth')
LOCATIONS = json.load(open('locations.json'))
VisitResult = namedtuple('VisitResult', 'visits,updated')

try:
    auth = json.load(open('auth.json'))
    access_token = '{app_id}|{app_secret}'.format_map(auth)
except FileNotFoundError:
    access_token = os.environ.get('ACCESS_TOKEN')


def get_for(date):
    date = date.replace(tzinfo='utc')
    for week in get_dates(access_token):
        for day, visits in week:
            if day == date:
                return VisitResult(
                    visits,      # visits for day
                    Arrow.now(AU_PERTH)  # when data was retrieved
                )
    return VisitResult([], Arrow.now(AU_PERTH))


class TimeCache(UserDict):
    def __init__(self, max_age, factory):
        super().__init__()
        self.max_age = max_age
        self.factory = factory

    def __setitem__(self, key, value):
        super().__setitem__(key, (Arrow.now(), value))

    def __getitem__(self, key):
        try:
            timestamp, value = super().__getitem__(key)
        except KeyError:
            regen = True
        else:
            regen = (Arrow.now() - timestamp) > self.max_age

        if regen:
            logging.info('Regenerating')
            self[key] = value = self.factory(key)

        return value


cached_get_for = TimeCache(ONE_HOUR, get_for).get


def make_link(date, name='index'):
    return url_for(name, date=date.isoformat())


def get_date_from_request():
    date = request.args.get('date')

    if date is not None:
        try:
            date = get_date(date)
        except (ValueError, TypeError, ParserError):
            pass

    if date == 'today':
        date = Arrow.now(AU_PERTH)

    if date is not None:
        try:
            date = date.floor('day')
        except AttributeError:
            # was invalid and stayed a string
            date = None

    return date


def get_visits_for_date(date):
    res = cached_get_for(date)
    if not res.visits:
        return VisitResult({}, res.updated)

    visits, updated = res
    visits = sorted(visits, key=itemgetter(0))
    visits = groupby(visits, key=itemgetter(0))
    visits = {k: list(map(itemgetter(1), v)) for k, v in visits}

    return VisitResult(visits, updated)


@app.errorhandler(400)
def custom400(error):
    return jsonify({
        'error': error.description,
        'status': 1
    })


@app.route('/index.json')
def index_json():
    date = get_date_from_request()

    if date is None:
        return abort(400, 'Invalid date provided')

    visits, updated = get_visits_for_date(date)

    return jsonify({
        'date': date.isoformat(),
        'updated': updated.isoformat(),
        'pagination': {
            "next": make_link(date + ONE_DAY, ".index_json"),
            "prev": make_link(date - ONE_DAY, ".index_json"),
        },
        'visits': visits,
        'status': 0
    })


@app.route('/')
def index():
    date = get_date_from_request()

    if date is None:
        # fill in missing values with defaults
        return redirect(url_for('.index', date='today'))

    visits, updated = get_visits_for_date(date)
    visits = sorted(visits.items())
    is_today = date.date() == Arrow.now(AU_PERTH).date()

    return render_template(
        'index.html',
        date=date,
        visits=visits,
        locations=LOCATIONS,
        updated=updated,
        is_today=is_today,
        next_page=make_link(date + ONE_DAY),
        prev_page=make_link(date - ONE_DAY)
    )


@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
