#! /usr/bin/env python3

import logging
import os, sys
import pytz
import re
import requests
from lxml import html
from datetime import datetime
from prometheus_client import CollectorRegistry, Gauge, Summary, push_to_gateway

LOGIN_PAGE      = 'https://www.puregym.com/Login/'
LOGOUT_PAGE     = 'https://www.puregym.com/logout/'
MEMBERS_PAGE    = 'https://www.puregym.com/members/'

EMAIL       = os.getenv("PUREGYM_EMAIL")
PIN         = os.getenv("PUREGYM_PIN")

PUSHGATEWAY  = os.getenv("PUREGYM_PUSHGATEWAY")
registry     = CollectorRegistry()
job_duration = Summary('puregym_job_duration', 'Time spent finding number of people', registry=registry)

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

@job_duration.time()
def main():
    log.debug("START: %s" % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    with requests.Session() as s:

        log.debug("====== Retrieving login page")
        ## This will redirect us to a different URL to login
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
            people = Gauge('puregym_people', "Number of people in PureGym", ["gym","gym_nice"], registry=registry)
            people.labels(gym=gym_ref, gym_nice=gym_nice).set(gym_people)

            now = datetime.now(pytz.timezone('Europe/London')).strftime('%Y-%m-%d %H:%M:%S')
            success = Gauge('puregym_last_success', "Epoch of last success", ["gym","gym_nice"], registry=registry)
            success.labels(gym=gym_ref, gym_nice=gym_nice).set_to_current_time()
            try:
                with open(LOGS+'/puregym.csv','a') as f:
                    f.write(now+','+str(gym_people)+"\n")
                log.debug("Log updated")
            except:
                log.critical("Failed to write stats to file")
                log.critical(now, gym_people)
                raise

        else:
            log.warning("Couldn't identify gym people :(")
            with open(LOGS+'/error_%s.html' % datetime.now(pytz.timezone('Europe/London')).strftime('%Y%m%d%H%M%S'), 'w') as f:
                f.write(mp.text)

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
    if PUSHGATEWAY is not None:
        log.debug("Sending metrics to Prometheus: %s", PUSHGATEWAY)
        try:
            push_to_gateway(PUSHGATEWAY, job='puregym', registry=registry)
        except:
            log.critical("Could not update Prometheus: %s", PUSHGATEWAY)
            raise
    else:
        log.debug("No Pushgateway set")
