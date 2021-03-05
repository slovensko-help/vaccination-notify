# Redis
REDIS_BASE = "redis://localhost:6379/"  # The base URL of a running Redis instance
REDIS_URL = REDIS_BASE + "2"            # (unused) The Redis database URL to use to store app data

# Celery
CELERY_BROKER_URL = REDIS_BASE + "3"      # The Redis database URL to use for Celery
CELERY_RESULT_BACKEND = REDIS_BASE + "3"  # The Redis database URL to use for Celery

# Flask
SECRET_KEY = ""                             # A secret key used in the app (for CSRF protection), generate with `openssl rand -hex 16`
SESSION_PROTECTION = "strong"               #
PREFERRED_URL_SCHEME = "https"              # Do https by default
SERVER_NAME = "localhost.localdomain:5000"  # The server name to use, use a fqdn here like: www.example.com

# SQLAlchemy
SQLALCHEMY_DATABASE_URI = "sqlite:////var/www/sqlite.db"  # The path to the SQLite database file, will be created if it does not exist.
SQLALCHEMY_TRACK_MODIFICATIONS = False                    #

# hCaptcha
HCAPTCHA_SECRET_KEY = ""  # The hCaptcha secret key
HCAPTCHA_SITEKEY = ""     # The hCaptcha sitekey

# Sentry
SENTRY_INGEST = ""        # The Sentry ingest URL (th full URL)
SENTRY_SAMPLE_RATE = 0    # Sentry transaction sample rate (not the error sample rate)

# Email
MAIL_SERVER = "mail.example.com"                # The outgoing SMTP server to use
MAIL_DEBUG = False                              # Whether to print out SMTP commands and responses (very verbose!)
MAIL_PORT = 465                                 # SMTP port to connect to
MAIL_USE_TLS = False                            # Whether to use STARTTLS
MAIL_USE_SSL = True                             # Whether to connect using SSL/TLS
MAIL_USERNAME = "username"                      # The username to use for auth
MAIL_PASSWORD = ""                              # The password to use for auth
MAIL_DEFAULT_SENDER = "covid19@example.com"     # The sender address
# MAIL_SUPPRESS_SEND = True                     # Whether to suppress all sending (for testing)

# App
QUERY_PERIOD = 60 * 5                           # How often to query the NCZI backend for data (in seconds)
QUERY_DELAY = 2                                 # How much to sleep between requests (in seconds)
GROUP_NOTIFICATION_BACKOFF = 1800               # The back-off time between consecutive notifications to the same user about free spots (in seconds)
SPOT_NOTIFICATION_BACKOFF = 1800                # The back-off time between consecutive notifications to the same user about new groups (in seconds)

EMAIL_ENABLED = True                            # Whether to allow email notifications
PUSH_ENABLED = True                             # Whether to allow PUSH notifications

API_USE = "proxy"  # or "nczi"                  # Whether to call the NCZI API directly or through the data.korona.gov.sk proxy
API_USE_AGGREGATE = True                        # Whether to use the get_all aggregate API

NCZI_GROUPS_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_vaccination_groups"
NCZI_PLACES_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_driveins_vacc"
NCZI_QUERY_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/validate_drivein_times_vacc"
NCZI_PLACES_ALL_URL = "https://mojeezdravie.nczisk.sk/api/v1/web/get_all_drivein_times_vacc"

PROXY_GROUPS_URL = "https://data.korona.gov.sk/ncziapi/get_vaccination_groups"
PROXY_PLACES_URL = "https://data.korona.gov.sk/ncziapi/get_driveins_vacc"
PROXY_QUERY_URL = "https://data.korona.gov.sk/ncziapi/validate_drivein_times_vacc"
PROXY_PLACES_ALL_URL = "https://data.korona.gov.sk/ncziapi/get_all_drivein_times_vacc"

NOTIFICATION_UNCONFIRMED_CLEAR = 7 * 24 * 3600  # Period after which an unconfirmed subscription is deleted (in seconds)
APP_SECRET = ""                                 # A different secret key for the app, used to generate the user secrets (generate with `openssl rand -hex 32`)
