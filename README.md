# vaccination-notify

## Usage

Setup the `TWILIO_SID`, `TWILIO_TOKEN` and `TWILIO_MSG_SERV_SID` environment variables to
the values of your Twilio account SID, Twilio auth token and a SID of some of
your messaging services (you have to create a new one in a new project by default).

Install the requirements using `pip install -r requirements.txt` (ideally into a virtual
environment).

The scripts below need up-to-date `places.json` and `groups.json` files, which contain
the list of vaccination places and vacicnation-eligible groups, respectively. To update these
files, run the `places.py` and `groups.py` scripts, respectively.

To get notified when there are free spots at some of the selected vaccination places
use the `track.py` script. The following command will notify the two mentioned numbers
if there are any free spots at vaccination places in Bratislava or Žilina, it will check
the form every 5 minutes.
```shell
> ./track.py -n +421123456789 -n +42100000000 -c Bratislava -c Žilina -f 5
```

To get notified when there is a new group of vaccination-eligible people use the
`wave.py` script. The following command will notify the two mentioned numbers if
there are new groups of vaccination-eligible people, it will query the form every
10 minutes.
```shell
> ./wave.py -n +421123456789 -n +42100000000 -f 10
```