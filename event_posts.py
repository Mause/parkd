from pprint import pprint

from dateutil.parser import parse
from arrow import Arrow
import requests

runi = lambda s: s.encode('cp850', errors='replace').decode('cp850')

BASE = 'https://graph.facebook.com/v2.0/'

DAYS = [
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday'
]


def arrow_parse(t):
    return Arrow.fromdate(parse(t))


def get_posts(access_token):
    r = requests.get(
        BASE + 'posts',
        params={
            'format': 'json',
            'id': 'parkdatcurtin',
            'access_token': access_token,
            'fields': 'updated_time,message',
            'limit': 50
        }
    )

    rj = r.json()
    if not r.ok:
        pprint(rj)
        assert r.ok

    return rj['data']


def get_date_posts(access_token):
    for post in get_posts(access_token):
        if 'message' not in post:
            # odd. why does this post not have a message?
            continue

        # ignore that which has nothing to do with what we need
        lines = post['message'].splitlines()
        for idx, line in enumerate(lines):
            if line.startswith('Monday'):

                post['message'] = '\n'.join(lines[idx:])
                yield post


def parse_day(day):
    for visit in day[1:]:
        if visit[0] != '*':
            yield ('', visit)

        elif '-' not in visit:
            # invalid, probably an announcment for that day
            continue

        else:
            location, visitors = visit[1:].split(' - ', 1)

            visitors = [
                visit
                .strip()
                .replace(b'\xe2\x80\x99'.decode(), "'")
                .replace(b'\xe2\x80\x93'.decode(), '-')
                for visit in visitors.split(',')
            ]

            for visitor in visitors:
                yield (location, visitor)


def parse_week(days):
    for day in days:
        day = day.splitlines()

        day_name, date = day[0].strip().split(' ', 1)
        if day_name.lower() not in DAYS:
            continue

        yield ((
            arrow_parse(date),
            list(parse_day(day))
        ))


def get_dates(access_token):
    for update in get_date_posts(access_token):
        days = update['message'].split('\n\n')

        yield parse_week(days)
