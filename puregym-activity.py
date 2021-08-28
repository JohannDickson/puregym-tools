#! /usr/bin/env python3

import logging
import os, sys
import pytz
import re
import requests
from lxml import html
from datetime import datetime, timedelta

LOGIN_PAGE      = 'https://www.puregym.com/Login/'
LOGOUT_PAGE     = 'https://www.puregym.com/logout/'
MEMBERS_PAGE    = 'https://www.puregym.com/members/'
ACTIVITY_PAGE   = 'https://www.puregym.com/members/activity'

EMAIL       = os.getenv("PUREGYM_EMAIL")
PIN         = os.getenv("PUREGYM_PIN")

LOGS        = "/tmp/"
MAIN_LOG    = os.path.join(LOGS, "puregym.log")
ERROR_LOG   = os.path.join(LOGS, "puregym-error.log")

CSV_FILE    = os.path.join(LOGS, "puregym.csv")
CSV_HEADER  = "Timestamp,People"

logformat = "%(levelname)s - %(message)s"
formatter = logging.Formatter(logformat)
log = logging.getLogger("puregym")
log.setLevel(logging.WARN)
ch = logging.StreamHandler()
ch.setFormatter(formatter)
log.addHandler(ch)

def main():
    log.debug("START: %s" % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    with requests.Session() as s:

        log.debug("====== Retrieving login page")
        log.debug(LOGIN_PAGE)
        l = s.get(LOGIN_PAGE)
        log.debug(l.status_code)
        if l.status_code != 200:
            log.critical("Failed to retrieve login page")
            log.critical(l.status_code)
            return

        if b"The members area and class booking are currently unavailable" in l.content:
            log.critical("Login page unavailable")
            with open(LOGS+'/error.html', 'w') as f:
                f.write(l.text)
            sys.exit(1)
        else:
            with open(LOGS+'/login.html', 'w') as f:
                f.write(l.text)

        tree = html.fromstring(l.content)
        tok = tree.xpath("//input[@name='__RequestVerificationToken']/@value")[0]
        log.debug("Token: "+tok)


        log.debug("====== Logging in")
        # Here we post the data back to the same page
        # Instead of to a login api
        log.debug(l.url)
        lr = s.post(l.url,
                data={
                    'username': EMAIL,
                    'password': PIN,
                    '__RequestVerificationToken': tok
                },
            )
        log.debug(lr.status_code)
        if lr.status_code != 200:
            log.critical("Failed to log in")
            log.critical(lr.status_code)
            return
        ## OIDC
        form = html.fromstring(lr.text).forms[0]
        la = form.submit()
        log.debug(la.status_code)
        if la.status_code != 200:
            log.critical("Failed to log in (OIDC)")
            log.critical(la.status_code)
            return


        log.debug("======== Retrieving activity page")
        log.debug(ACTIVITY_PAGE)
        ap = s.get(ACTIVITY_PAGE)
        log.debug(ap.status_code)
        if ap.status_code != 200:
            log.critical("Failed to retrieve activity page")
            log.critical(ap.status_code)
            return

        log.debug("Finding most recent activity..")
        try:
            tree = html.fromstring(ap.content)
            activity_history = tree.xpath("//div[@class='calendar-column']/ul/li/div")
            log.debug("%s Activities found", len(activity_history))

            most_recent = activity_history[0].xpath("./div/text()")
            (date, time, gym, workout, duration) = most_recent
            log.debug("Most recent: %s", most_recent)

            minutes = int(re.findall(r'^\d+', duration)[0])
            hhmm = str(timedelta(minutes=minutes))

            output = ','.join([f'{date} {time}', hhmm, workout])
            print(output)

        except:
            raise

        log.debug("Logging out")
        # we get a first page
        lo = s.get(LOGOUT_PAGE)
        log.debug(lo.status_code)
        # which contains an iframe
        logout = html.fromstring(lo.text).xpath('//iframe')[0]
        log.debug(logout.attrib.get('src'))
        p = s.get(logout.attrib.get('src'))
        log.debug(lr.status_code)
        # which also has an iframe
        logout = html.fromstring(p.text).xpath('//iframe')[0]
        log.debug(logout.attrib.get('src'))
        f = s.get(logout.attrib.get('src'))
        log.debug(f.status_code)
        # and then it is done

    log.debug("END: %s" % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    main()
