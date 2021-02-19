# vaccination-notify

This project provides a way to get notifications on free vaccination spots in the Slovak COVID-19
vaccination registration form at <https://www.old.korona.gov.sk/covid-19-vaccination-form.php>.

## Usage (server)

The service is provided via a Flask app on Python 3 (see [vacnotify](vacnotify/__init__.py)) that can
be run using any WSGI server (or the development server bundled with Flask by using `flask run`).

### Requirements

See the [requirements.txt](requirements.txt) file for Python requirements. On top of that:
 - OpenSSL is required to generate an ECC keypaid for use in VAPID for Web Push notifications,
 - Redis is required as a backend for the Celery task queue,
 - Celery is required as a task queue to run the data queries and send notifications,
 - An outbound SMTP server or a Mailgun setup is required to send out the email notifications.

### Setup

1. Make a virtual environment.

   `python3 -m venv virt`

2. Activate it.

   `. virt/bin/activate`

3. Install the requirements.

   `pip install -r requirements.txt`

4. Create the `instance` directory, it is used or files specific to the
running instance of the service, like configuration files.
5. Generate an ECC keypair to be used in VAPID for WebPush notifications:

    `openssl ecparam -name prime256v1 -genkey -noout -out instance/vapid_private.pem`

6. Separate the public key and private keys into files with just the DER encoded values:

    ```
    openssl ec -in instance/vapid_private.pem -pubout -outform DER | tail -c 65 | base64 | tr -d "=\n" | tr "/+" "_-" > instance/vapid_pubkey.der
    openssl ec -in instance/vapid_private.pem -outform DER | tail -c +8 | head -c 32 | base64 | tr -d '=' |tr '/+' '_-' > instance/vapid_privkey.der`
    ```

7. Create the `claims.json` file in the instance directory with the VAPID claims structure:

    `{"sub": "mailto:some.address.for.an.admin@domain.com"}`

8. Create the `alerts.json` file in the instance directory that lists the alerts currently displayed on the page.
   The format is simple, a list of dictionaries with the `icon`, `text` and `class` keys. An empty list is necessary if
   there are no alerts.
   
9. Create the `config.py` file in the instance directory, see the [example.config.py](example.config.py) file.

10. Initialize the database.

    `env FLASK_ENV=development FLASK_APP=vacnotify flask db upgrade`


### Debug

Start a local Redis server, using service setup for your distribution. Then:

```shell
> env FLASK_ENV=development celery -A vacnotify.celery worker --concurrency 2 -B -s celerybeat-schedule --detach --loglevel INFO -f celery.log
> env FLASK_ENV=development FLASK_APP=vacnotify flask run
```

### Production

Use uWSGI and its `smart-attach-daemon` to start Celery. Start Redis as a service manually.
Don't forget to restart celery if changes to its tasks are made (restarting uWSGI will not kill it).

The below is a working uWSGI setup (works on Ubuntu 20.04 with the project at `/var/www`).
```ini
[uwsgi]
uid = www-data
gid = www-data

plugin = python3
base = /var/www
chdir = %(base)

#python module to import
app = vacnotify
module = %(app)
virtualenv = %(base)/virt3
#the variable that holds a flask application inside the module imported at line #6
callable = app

enable-threads = true
env = FLASK_ENV=production

socket = /run/uwsgi/app/covid/covid.sock
chmod-socket = 666
chown-socket = www-data

smart-attach-daemon = /tmp/celery_covid.pid %(virtualenv)/bin/celery -A vacnotify.celery worker -B -s /tmp/celery_covid.beat --loglevel INFO --pidfile /tmp/celery_covid.pid -f %(base)/log/celery.log

logto = %(base)/log/uwsgi.log

master = true
workers = 2
```

Restarting celery with the setup as above is done by killing the process with the pid stored at `/tmp/celery_covid.pid`.
Reloading the Flask app can be done by reloading the uWSGI master (`systemctl reload uwsgi`).

The following nginx setup then passes requests to the running Flask app on uWSGI.
```
    location / {
        include         uwsgi_params;
        uwsgi_param Host $host;
        uwsgi_param X-Real-IP $remote_addr;

        uwsgi_pass  unix:/run/uwsgi/app/covid/socket;
    }
    
    location /static/ {
        root      /var/www/vacnotify;
        gzip      on;
        expires   7d;
        tcp_nodelay off;
        try_files /$uri =404;
    }
```

## Usage (scripts)

**The setup below is outdated, there are now rate limits on the API that will stop the script
from working.**

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

