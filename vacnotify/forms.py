from wtforms import validators, SelectMultipleField
from wtforms.fields.html5 import EmailField
from flask_wtf import FlaskForm
from wtforms.widgets import ListWidget, CheckboxInput


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class SpotSubscriptionForm(FlaskForm):
    email = EmailField("email", [validators.DataRequired(), validators.Email(), validators.Length(max=128)])
    places = MultiCheckboxField("places", [validators.DataRequired()], coerce=int)


class GroupSubscriptionForm(FlaskForm):
    email = EmailField("email", [validators.DataRequired(), validators.Email(), validators.Length(max=128)])
