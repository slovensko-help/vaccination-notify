# vaccination-notify

This project provides a way to get notifications on free vaccination spots in the
NCZI COVID-19 vaccination form at <https://www.old.korona.gov.sk/covid-19-vaccination-form.php>.
There are standalone scripts which you can run to get notified via SMS (provided you have a Twilio account) and
also a web service which servers as a frontend for these requests to get notified.

## Usage (scripts)

Setup the `TWILIO_SID`, `TWILIO_TOKEN` and `TWILIO_MSG_SERV_SID` environment variables to
the values of your Twilio account SID, Twilio auth token and a SID of some of
your messaging services (you have to create a new one in a new project by default).

Install the requirements using `pip install -r requirements.txt` (ideally into a virtual
environment).

The scripts below need up-to-date `places.json` and `groups.json` files, which contain
the list of vaccination places and vaccination-eligible groups, respectively. To update these
files, run the `places.py` and `groups.py` scripts, respectively.

To get notified when there are free spots at some of the selected vaccination places
use the `track.py` script. The following command will notify the two mentioned numbers
if there are any free spots at vaccination places in Bratislava or Žilina, it will check
the form every 5 minutes.
```shell
> scripts/track.py -n +421123456789 -n +42100000000 -c Bratislava -c Žilina -f 5
```

To get notified when there is a new group of vaccination-eligible people use the
`wave.py` script. The following command will notify the two mentioned numbers if
there are new groups of vaccination-eligible people, it will query the form every
10 minutes.
```shell
> scripts/wave.py -n +421123456789 -n +42100000000 -f 10
```

## Usage (server)


### Debug
```shell
> env FLASK_ENV=development celery -A vacnotify.celery worker --concurrency 2 -B -s celerybeat-schedule --detach --loglevel INFO -f celery.log
> env FLASK_ENV=development FLASK_APP=vacnotify flask run
```
