import os
import json
import logging
from datetime import timedelta
from collections import namedtuple, defaultdict

import dill
import flask
import bmemcached
from arrow import Arrow
import dateutil.tz as dateutil_tz
from arrow import get as get_date
from arrow.parser import ParserError
from flask import request, redirect, url_for, render_template, abort, jsonify

from config import access_token
from via_website import get_dates

logging.basicConfig(level=logging.INFO)
app = flask.Flask(__name__)

ONE_DAY = timedelta(days=1)
ONE_HOUR = timedelta(hours=1)
AU_PERTH = dateutil_tz.gettz('Australia/Perth')
with open('locations.json') as fh:
    LOCATIONS = json.load(fh)
VisitResult = namedtuple('VisitResult', 'visits,updated')


class TimeCache():
    def __init__(self, max_age):
        self.mc = bmemcached.Client(
            os.environ.get(
                'MEMCACHEDCLOUD_SERVERS',
                'localhost:11211'
            ).split(','),
            os.environ.get(
                'MEMCACHEDCLOUD_USERNAME',
                ''
            ),
            os.environ.get(
                'MEMCACHEDCLOUD_PASSWORD',
                ''
            ),
            pickler=dill.Pickler,
            unpickler=dill.Unpickler
        )

        self.max_age = max_age

    def set(self, key, value):
        key = key.isoformat()
        logging.info('Writing data for %s to cache', key)
        self.mc.set('permanent-' + key, value)
        self.mc.set('transient-' + key, value, self.max_age)

    def try_transient(self, key):
        return self.mc.get('transient-' + key.isoformat())

    def try_refresh(self, date):
        date = date.replace(tzinfo='utc')
        weeks = get_dates(access_token)

        dates = {
            day: VisitResult(
                list(visits),        # visits for day
                Arrow.now(AU_PERTH)  # when data was retrieved
            )
            for week in weeks
            for day, visits in week
        }

        # cache everything we're given
        for day, visits in dates.items():
            self.set(day, visits)

        return dates.get(date)

    def try_permanent(self, key):
        return self.mc.get('permanent-' + key.isoformat())

    def get(self, key):
        logging.info('Resolving for %s', key)


        funcs = [
            self.try_transient,
            self.try_refresh,
            self.try_permanent
        ]

        for func in funcs:
            name = func.__name__[4:].title()

            logging.info('Trying %s', name)
            value = func(key)

            if value and value.visits:
                logging.info('%s succeeded', name)

                logging.info('Visits: %d', len(value.visits))

                if name != 'transient':
                    self.set(key, value)  # cache it!

                return value

        logging.info(
            "Data not available from the website or the cache"
        )

        # default
        return VisitResult([], Arrow.now(AU_PERTH))


cached_get_for = TimeCache(int(ONE_HOUR.total_seconds())).get


def make_link(date, name='index'):
    return url_for(name, date=date.isoformat(), _external=True)


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
        logging.info('No visits available?')
        return VisitResult({}, res.updated)

    visits, updated = res

    # <group by location>
    sorted_visits = defaultdict(list)
    for location, visit in visits:
        sorted_visits[location].append(visit)
    # </group by location>

    return VisitResult(sorted_visits, updated)


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
    app.debug = 'ON_HEROKU' not in os.environ
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
