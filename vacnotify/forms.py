import math

from markupsafe import Markup
from wtforms import validators, SelectMultipleField
from wtforms.fields.html5 import EmailField
from flask_wtf import FlaskForm
from wtforms.widgets import CheckboxInput, html_params
from werkzeug.utils import escape


class ListWidget(object):
    def __init__(self, prefix_label=True):
        self.prefix_label = prefix_label

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        size = kwargs.get("size", 1)
        field_kwargs = kwargs.get("field_kwargs", {})
        html = [f'<div class="row" {html_params(**kwargs)}>']
        fields = [(subfield(**field_kwargs), subfield.label) for subfield in field]
        total = len(fields)
        col = math.ceil(total / size)
        for i in range(size):
            html.append('<div class="col-sm">')
            html.append(f'<div class="list-group">')
            for j in range(col):
                idx = i * col + j
                if idx >= total:
                    break
                subfield, label = fields[idx]
                if self.prefix_label:
                    html.append(f'<label class="list-group-item form-check-label">{escape(label)} {subfield}</label>')
                else:
                    html.append(f'<label class="list-group-item form-check-label">{subfield} {escape(label)}</label>')
            html.append(f'</div>')
            html.append("</div>")
        html.append("</div>")
        return Markup(''.join(html))


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class SpotSubscriptionForm(FlaskForm):
    email = EmailField("email", [validators.DataRequired(), validators.Email(), validators.Length(max=128)])
    places = MultiCheckboxField("places", [validators.DataRequired()], coerce=int)


class GroupSubscriptionForm(FlaskForm):
    email = EmailField("email", [validators.DataRequired(), validators.Email(), validators.Length(max=128)])
