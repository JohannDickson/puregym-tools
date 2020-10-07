#! /usr/bin/env python3

import logging
import os, sys
import pytz
import re
import requests
from lxml import html
from datetime import datetime
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

LOGIN_PAGE      = 'https://www.puregym.com/Login/'
LOGOUT_PAGE     = 'https://www.puregym.com/logout/'
LOGIN_API       = 'https://www.puregym.com/api/members/login'
MEMBERS_PAGE    = 'https://www.puregym.com/members/'

EMAIL       = os.getenv("PUREGYM_EMAIL")
PIN         = os.getenv("PUREGYM_PIN")

PUSHGATEWAY = os.getenv("PUREGYM_PUSHGATEWAY")

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
    registry = CollectorRegistry()
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
        log.debug(LOGIN_API)
        lr = s.post(LOGIN_API,
                headers={'__requestverificationtoken': tok},
                data={'email': EMAIL, 'pin': PIN},
            )
        log.debug(lr.status_code)
        if lr.status_code != 200:
            log.critical("Failed to log in")
            log.critical(lr.status_code)
            return


        log.debug("======== Retrieving members page")
        log.debug(MEMBERS_PAGE)
        mp = s.get(MEMBERS_PAGE)
        log.debug(mp.status_code)
        if mp.status_code != 200:
            log.critical("Failed to retrieve members page")
            log.critical(mp.status_code)
            return

        log.debug("Finding number of people..")
        try:
            rex = re.findall(r'there are.*\>(\d+) (?:or fewer )?(?:of \d+ )?people', mp.text)
            log.debug(rex)
        except:
            log.critical("Could not find people")
            raise

        log.debug("Finding Gym ref and name..")
        try:
            grex = re.findall(r'in.*href=\"/gyms/(.*)\">(.*)</a> right now', mp.text)
            log.debug(grex)
        except:
            log.critical("Could not find gym ref/name")

        if len(grex) == 1 and len(grex[0]) == 2:
            (gym_ref, gym_nice) = grex[0]

        if len(rex) == 1 and int(rex[0])>=0:
            gym_people = rex[0]
            log.info("There are %s people in %s", gym_people, gym_nice)

            now = datetime.now(pytz.timezone('Europe/London')).strftime('%Y-%m-%d %H:%M:%S')
            try:
                with open(LOGS+'/puregym.csv','a') as f:
                    f.write(now+','+str(gym_people)+"\n")
                log.debug("Log updated")
            except:
                log.critical("Failed to write stats to file")
                log.critical(now, gym_people)
                raise

            if PUSHGATEWAY is not None:
                log.debug("Sending metrics to Prometheus: %s", PUSHGATEWAY)
                try:
                    g = Gauge('puregym_people', "Number of people in PureGym", ["gym","gym_nice"], registry=registry)
                    g.labels(gym=gym_ref, gym_nice=gym_nice).set(gym_people)
                    push_to_gateway(PUSHGATEWAY, job='puregym', registry=registry)

                except:
                    log.critical("Could not update Prometheus: %s", PUSHGATEWAY)
                    raise
            else:
                log.debug("No Pushgateway set")

        else:
            log.warn("Couldn't identify gym people :(")
            with open(LOGS+'/error_%s.html' % datetime.now(pytz.timezone('Europe/London')).strftime('%Y%m%d%H%M%S'), 'w') as f:
                f.write(mp.text)

        log.debug("Logging out")
        s.get(LOGOUT_PAGE)

    log.debug("END: %s" % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    main()
