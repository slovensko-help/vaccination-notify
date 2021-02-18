import math

from markupsafe import Markup
from wtforms import validators, SelectMultipleField, Label, HiddenField, ValidationError
from wtforms.fields.html5 import EmailField
from flask_wtf import FlaskForm
from wtforms.widgets import CheckboxInput, html_params
from werkzeug.utils import escape


class CityListWidget(object):
    def __init__(self, prefix_label=True):
        self.prefix_label = prefix_label

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
                city = choice_map[data]
                label_content = escape(city.name)
                if city.free_online:
                    label_content += Markup(' <i class="fas fa-check-circle fa-xs" title="Mesto má voľné termíny."></i>')
                label = Label(id, label_content)
                if self.prefix_label:
                    html.append(f'<div class="govuk-checkboxes__item">{label(class_="govuk-label govuk-checkboxes__label")} {subfield}</div>')
                else:
                    html.append(f'<div class="govuk-checkboxes__item">{subfield} {label(class_="govuk-label govuk-checkboxes__label")}</div>')
            html.append(f'</div>')
            html.append("</div>")
        html.append("</div>")
        return Markup(''.join(html))


class MultiCheckboxField(SelectMultipleField):
    widget = CityListWidget(prefix_label=False)
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
    cities = MultiCheckboxField("cities", [validators.DataRequired(message="Výber miest je povinný.")], coerce=int)


class GroupSubscriptionForm(SubscriptionForm):
    pass
