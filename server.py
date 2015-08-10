import json
import logging
from datetime import timedelta
from functools import lru_cache
from operator import itemgetter
from itertools import groupby

import flask
from arrow import Arrow
from arrow import get as get_date
from flask import request, redirect, url_for, render_template
from event_posts import get_dates as get_dates

logging.basicConfig(level=logging.INFO)
app = flask.Flask(__name__)


auth = json.load(open('auth.json'))
access_token = '{app_id}|{app_secret}'.format_map(auth)


@lru_cache(10)
def get_for(date):
    date = date.replace(tzinfo='utc')
    for week in get_dates(access_token):
        for day, visits in week:
            if day == date:
                return (day, visits)
    return None


def make_link(date):
    return url_for('index', date=date.isoformat())


@app.route('/')
def index():
    date = request.args.get('date')

    if date is not None:
        try:
            date = get_date(date).floor('day')
        except (ValueError, TypeError):
            pass

    if date is None:
        # fill in missing values with defaults
        return redirect(
            url_for('.index', date=Arrow.now().floor('day'))
        )

    res = get_for(date)
    if res:
        _, visits = res
        visits = sorted(visits, key=itemgetter(0))
        visits = groupby(visits, key=itemgetter(0))
        visits = {k: list(map(itemgetter(1), v)) for k, v in visits}

    else:
        visits = {}

    one_day = timedelta(days=1)

    return render_template(
        'index.html',
        date=date,
        visits=visits,
        next_page=make_link(date + one_day),
        prev_page=make_link(date - one_day)
    )


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')
