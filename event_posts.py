import sys
sys.path.insert(0, 'ics.py')

from pprint import pprint
from itertools import islice
from operator import itemgetter

from dateutil.parser import parse
from ics import Calendar, Event
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


def serialize(week):
    for dates in week:
        events_in_week = []

        for day, visits in dates:
            for location, visitor in visits:
                e = Event()

                e.begin = day
                e.location = location if location else None
                e.name = visitor

                events_in_week.append(e)

        yield events_in_week


def print_raw(raw):
    lines = raw.splitlines()

    def inner(indent=0):
        while lines:
            line = lines.pop(0)

            if line.startswith('BEGIN'):
                print('\t' * indent + line)
                inner(indent+1)
            elif line.startswith('END'):
                print('\t' * (indent - 1) + line)
                return
            else:
                print('\t' * indent + line)

    return inner()


def main():
    dates = get_dates()

    day, visits = next(next(dates))
    print(day.strftime('%d/%m/%Y'))

    places = map(itemgetter(0), visits)
    just = max(map(len, places)) + 1

    print('\n'.join(
        '{} -> {}'.format(visit[0].rjust(just), visit[1])
        for visit in visits
    ))
    return

    Arrow.strftime = lambda self, format: self

    c = Calendar()
    events = serialize(dates)

    c.events = list(events)[0]  # only add the first week

    print(len(c.events))

    # for event in c.events:
    #     # print(event.begin, end=' ')
    #     event.make_all_day()
    #     # print(event.begin)

    # # import IPython
    # # IPython.embed()

    # print_raw(str(c))

    pprint(sorted(c.events))

    # # for event in c.events:
    # #     print(runi(repr(event)))
    # #     for k, v in vars(event).items():
    # #         print(k, end=' ')
    # #         print(v)
    # pprint(c.events)
    # # pprint(list(map(repr, c.events)))

    # with open('my.ics', 'w') as fh:
    #     fh.writelines(c)

    #     print('-> Stalls')
    #     for location, visitors in visits['stalls'].items():
    #         print('@', location)
    #         for visitor in visitors:
    #             try:
    #                 print('*', visitor)
    #             except UnicodeEncodeError:
    #                 print('*', visitor.encode())

    #     print('-> Misc.', ...)
    #     for dynamic_event in visits['misc']:
    #         print('->', dynamic_event)

    #     print()


if __name__ == '__main__':
    main()
