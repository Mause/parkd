import calendar

import requests
from arrow import Arrow
from lxml.html import fromstring
from dateutil.parser import parse

URL = 'http://news.curtin.edu.au/events/parkd-curtin/'
ENDASH = b'\xe2\x80\x93'.decode()


def get_content():
    xml = requests.get(URL).text
    xml = xml.replace(b'\u2013'.decode(), '')
    xml = fromstring(xml)

    return xml.xpath('.//div[@class="editable-content"]')[0]


def parse_days(content):
    for h2 in content.xpath('.//h2'):
        ul = h2.getnext()

        title = h2.text
        if not title or title.split()[0] not in calendar.day_name:
            continue

        yield h2.text, [li.text for li in ul.xpath('.//li')]


def parse_locations(locations):
    for location in locations:
        location = location.split(
            ENDASH
            if ENDASH in location
            else
            '-',
            1
        )

        location, visits = map(str.strip, location)

        for visit in visits.replace('\xa0', ' ').split(', '):
            yield (location, visit.strip())


def get_dates(_):
    days = parse_days(get_content())
    # we used to be able to support previous weeks; each item is a week
    return [
        (
            (
                Arrow.fromdatetime(parse(day)),
                parse_locations(locations)
            )
            for day, locations in days
        )
    ]
