import datetime

from peewee import BooleanField, DateTimeField, ForeignKeyField, TimeField, DateField
from wtforms import fields, form, widgets
from wtforms.fields import FormField, _unset_value
from wtforms.widgets import HTMLString, html_params

from wtfpeewee.fields import ModelSelectField, ModelHiddenField
from wtfpeewee.orm import ModelConverter


class BooleanSelectField(fields.SelectFieldBase):
    widget = widgets.Select()

    def iter_choices(self):
        yield ('1', 'True', self.data)
        yield ('', 'False', not self.data)

    def process_data(self, value):
        try:
            self.data = bool(value)
        except (ValueError, TypeError):
            self.data = None

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = bool(valuelist[0])
            except ValueError:
                raise ValueError(self.gettext(u'Invalid Choice: could not coerce'))


class CustomTimeField(fields.Field):
    widget = widgets.TextInput()

    def __init__(self, label=None, validators=None, format='%H:%M:%S', **kwargs):
        super(CustomTimeField, self).__init__(label, validators, **kwargs)
        self.format = format

    def _value(self):
        if self.raw_data:
            return u' '.join(self.raw_data)
        else:
            return self.data and self.data.strftime(self.format) or u''

    def process_formdata(self, valuelist):
        if valuelist:
            date_str = u' '.join(valuelist)
            try:
                self.data = datetime.datetime.strptime(date_str, self.format).time()
            except ValueError:
                try:
                    self.data = datetime.datetime.strptime(date_str, '%H:%M').time()
                except ValueError:
                    self.data = None
                    raise ValueError(self.gettext(u'Not a valid time value'))


def inject_class(kwargs, *klasses):
    i_class = list(klasses)
    copy = dict(kwargs)
    if 'class' in copy:
        i_class.append(copy.pop('class'))
    copy['class'] = ' '.join(i_class)
    return copy

def datetime_widget(field, **kwargs):
    kwargs.setdefault('id', field.id)
    html = []
    for subfield in field:
        if isinstance(subfield, fields.DateField):
            kwarg_copy = inject_class(kwargs, 'date-widget', 'datetime-widget')
        elif isinstance(subfield, CustomTimeField):
            kwarg_copy = inject_class(kwargs, 'time-widget', 'datetime-widget')
        html.append(subfield(**kwarg_copy))

    return HTMLString(u''.join(html))

class _DateTimeForm(form.Form):
    date = fields.DateField()
    time = CustomTimeField()

class CustomDateTimeField(FormField):
    widget = staticmethod(datetime_widget)

    def __init__(self, label='', validators=None, **kwargs):
        validators = None
        super(CustomDateTimeField, self).__init__(
            _DateTimeForm, label, validators,
            **kwargs
        )

    def process(self, formdata, data=_unset_value):
        prefix = self.name + self.separator
        kwargs = {}
        if data is _unset_value:
            try:
                data = self.default()
            except TypeError:
                data = self.default
        
        if data and data is not _unset_value:
            kwargs['date'] = data.date()
            kwargs['time'] = data.time()

        self.form = self.form_class(formdata, prefix=prefix, **kwargs)
    
    def populate_obj(self, obj, name):
        setattr(obj, name, self.data)

    @property
    def data(self):
        if self.date.data is not None and self.time.data is not None:
            return datetime.datetime.combine(self.date.data, self.time.data)


class CustomModelConverter(ModelConverter):
    def __init__(self, model_admin, additional=None):
        super(CustomModelConverter, self).__init__(additional)
        self.model_admin = model_admin
        self.converters[BooleanField] = self.handle_boolean
        self.converters[DateTimeField] = self.handle_datetime
        self.converters[TimeField] = self.handle_time
        self.converters[DateField] = self.handle_date

    def handle_boolean(self, model, field, **kwargs):
        return field.name, BooleanSelectField(**kwargs)
    
    def handle_datetime(self, model, field, **kwargs):
        return field.name, CustomDateTimeField(**kwargs)
    
    def handle_time(self, model, field, **kwargs):
        return field.name, CustomTimeField(**kwargs)
    
    def handle_date(self, model, field, **kwargs):
        return field.name, fields.DateField(**inject_class(kwargs, 'date-widget'))

    def handle_foreign_key(self, model, field, **kwargs):
        if field.null:
            kwargs['allow_blank'] = True

        if field.name in (self.model_admin.foreign_key_lookups or ()):
            form_field = ModelHiddenField(model=field.to, **kwargs)
        else:
            form_field = ModelSelectField(model=field.to, **kwargs)
        return field.name, form_field
