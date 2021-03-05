import math

from markupsafe import Markup
from wtforms import validators, SelectMultipleField, Label, HiddenField, ValidationError, TextAreaField
from wtforms.fields.html5 import EmailField
from flask_wtf import FlaskForm
from wtforms.widgets import CheckboxInput, html_params
from werkzeug.utils import escape


class CheckBoxListWidget(object):

    def __init__(self, labeler):
        self._labeler = labeler

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        size = kwargs.get("size", 1)
        if "size" in kwargs:
            del kwargs["size"]
        field_kwargs = kwargs.get("field_kwargs", {})
        if "field_kwargs" in kwargs:
            del kwargs["field_kwargs"]
        html = [f'<div class="govuk-grid-row" {html_params(**kwargs)}>']
        choice_map = {id: choice for id, choice in field.choices}
        fields = [(subfield.id, subfield.data, subfield(**field_kwargs)) for subfield in field]
        total = len(fields)
        col = math.ceil(total / size)
        col_class = {
            1: "govuk-grid-column-full",
            2: "govuk-grid-column-one-half",
            3: "govuk-grid-column-one-third"
        }.get(size, "govuk-grid-column-full")
        for i in range(size):
            html.append(f'<div class="{col_class}">')
            html.append(f'<div class="govuk-checkboxes" data-module="govuk-checkboxes">')
            for j in range(col):
                idx = i * col + j
                if idx >= total:
                    break
                id, data, subfield = fields[idx]
                choice = choice_map[data]
                label_content = self._labeler(choice)
                label = Label(id, label_content)
                html.append(f'<div class="govuk-checkboxes__item">{subfield} {label(class_="govuk-label govuk-checkboxes__label")}</div>')
            html.append(f'</div>')
            html.append("</div>")
        html.append("</div>")
        return Markup(''.join(html))


class CityListWidget(CheckBoxListWidget):

    def __init__(self):
        def city_label(city):
            label_content = escape(city.name)
            if city.free_online:
                label_content += Markup(' <i class="fas fa-check-circle fa-xs" title="Mesto má voľné termíny."></i>')
            return label_content
        super().__init__(city_label)


class MultiCheckboxField(SelectMultipleField):
    widget = CheckBoxListWidget(str)
    option_widget = CheckboxInput()


class CityMultiCheckboxField(SelectMultipleField):
    widget = CityListWidget()
    option_widget = CheckboxInput()


def encoding(which, message=None):
    if message is None:
        message = f"The value contains illegal characters, can only contain {which} characters."

    def _encoding(form, field):
        try:
            field.data.encode(which)
        except UnicodeEncodeError:
            raise ValidationError(message)
    return _encoding


class SubscriptionForm(FlaskForm):
    email = EmailField("email", [validators.Length(max=128, message="Maximálna dĺžka emailu je 128 znakov."), encoding("ascii", "Email obsahuje nepovolen=e znaky")])
    push_sub = HiddenField("push_sub", [validators.Length(max=5000)])

    def validate(self):
        if self.email.data:
            valid = super().validate({"email": [validators.Email(message="Email nemá správny formát."), validators.DataRequired(message="Email je povinný.")],
                                      "push_sub": [validators.Length(max=0)]})
        elif self.push_sub.data:
            valid = super().validate({"push_sub": [validators.DataRequired()],
                                      "email": [validators.Length(max=0)]})
        else:
            valid = False
        return valid


class SpotSubscriptionForm(SubscriptionForm):
    cities = CityMultiCheckboxField("cities", [validators.DataRequired(message="Výber miest je povinný.")], coerce=int)


class GroupSubscriptionForm(SubscriptionForm):
    pass


class UnsubscriptionForm(FlaskForm):
    id = HiddenField("id", [validators.DataRequired()])
    secret = HiddenField("secret", [validators.DataRequired()])
    reasons = MultiCheckboxField("reasons", [validators.DataRequired()],
                                 choices=[("found-here", "Vďaka notifikácii som našiel miesto/skupinu."),
                                          ("found-elsewhere", "Našiel som miesto/skupinu inde."),
                                          ("too-many", "Notifikácií je príliš."),
                                          ("other", "Iné.")])
    feedback = TextAreaField("feedback", [validators.Length(max=1000)])
