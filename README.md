# puregym-tools

This repository contains two scripts to help scrape some information off of the puregym's member page:
- number of people currently in your local gym
- your most recent activity


## Environment variables

To run these scripts, the following environment variables are required:
- `PUREGYM_EMAIL`
- `PUREGYM_PIN`

Optionally, to export the people counter to a prometheus pushgateway:
- `PUREGYM_PUSHGATEWAY`: url of the pushgateway
