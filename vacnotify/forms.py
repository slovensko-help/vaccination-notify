import math

from markupsafe import Markup
from wtforms import validators, SelectMultipleField, Label
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
        field_kwargs = kwargs.get("field_kwargs", {})
        html = [f'<div class="row" {html_params(**kwargs)}>']
        choice_map = {id: choice for id, choice in field.choices}
        fields = [(subfield.id, subfield.data, subfield(**field_kwargs)) for subfield in field]
        total = len(fields)
        col = math.ceil(total / size)
        for i in range(size):
            html.append('<div class="col-sm">')
            html.append(f'<div class="list-group">')
            for j in range(col):
                idx = i * col + j
                if idx >= total:
                    break
                id, data, subfield = fields[idx]
                city = choice_map[data]
                label_content = escape(city.name)
                if city.free_online:
                    label_content += Markup(' <i class="fas fa-check-circle fa-xs text-success" title="Mesto má voľné termíny." data-toggle="tooltip"></i>')
                label = Label(id, label_content)
                if self.prefix_label:
                    html.append(f'<label class="list-group-item form-check-label">{label} {subfield}</label>')
                else:
                    html.append(f'<label class="list-group-item form-check-label">{subfield} {label}</label>')
            html.append(f'</div>')
            html.append("</div>")
        html.append("</div>")
        return Markup(''.join(html))


class MultiCheckboxField(SelectMultipleField):
    widget = CityListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class SpotSubscriptionForm(FlaskForm):
    email = EmailField("email", [validators.DataRequired(), validators.Email(), validators.Length(max=128)])
    cities = MultiCheckboxField("cities", [validators.DataRequired()], coerce=int)


class GroupSubscriptionForm(FlaskForm):
    email = EmailField("email", [validators.DataRequired(), validators.Email(), validators.Length(max=128)])
