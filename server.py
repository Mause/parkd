import os
import json
import logging
from datetime import timedelta
from functools import lru_cache
from operator import itemgetter
from itertools import groupby

import flask
from arrow import Arrow
from arrow import get as get_date
from flask import request, redirect, url_for, render_template, abort, jsonify
from event_posts import get_dates as get_dates

logging.basicConfig(level=logging.INFO)
app = flask.Flask(__name__)

ONE_DAY = timedelta(days=1)


try:
    auth = json.load(open('auth.json'))
    access_token = '{app_id}|{app_secret}'.format_map(auth)
except FileNotFoundError:
    access_token = os.environ.get('ACCESS_TOKEN')


@lru_cache(10)
def get_for(date):
    date = date.replace(tzinfo='utc')
    for week in get_dates(access_token):
        for day, visits in week:
            if day == date:
                return (day, visits)
    return None


def make_link(date, name='index'):
    return url_for(name, date=date.isoformat())


def get_date_from_request():
    date = request.args.get('date')

    if date is not None:
        try:
            date = get_date(date).floor('day')
        except (ValueError, TypeError):
            pass

    return date


def get_visits_for_date(date):
    res = get_for(date)
    if res:
        _, visits = res
        visits = sorted(visits, key=itemgetter(0))
        visits = groupby(visits, key=itemgetter(0))
        visits = {k: list(map(itemgetter(1), v)) for k, v in visits}

    else:
        visits = {}

    return visits


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

    visits = get_visits_for_date(date)

    return jsonify({
        'date': date.isoformat(),
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
        return redirect(
            url_for('.index', date=Arrow.now().floor('day'))
        )

    visits = get_visits_for_date(date)
    visits = sorted(visits.items())
    is_today = date.date() == Arrow.now().date()

    return render_template(
        'index.html',
        date=date,
        visits=visits,
        is_today=is_today,
        next_page=make_link(date + ONE_DAY),
        prev_page=make_link(date - ONE_DAY)
    )


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
