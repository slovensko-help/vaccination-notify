from wtforms import validators, SelectMultipleField
from wtforms.fields.html5 import EmailField
from flask_wtf import FlaskForm


class SpotSubscriptionForm(FlaskForm):
    email = EmailField("email", [validators.DataRequired(), validators.Email(), validators.Length(max=128)])
    places = SelectMultipleField("places")


class GroupSubscriptionForm(FlaskForm):
    email = EmailField("email", [validators.DataRequired(), validators.Email(), validators.Length(max=128)])
