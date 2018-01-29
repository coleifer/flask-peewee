from peewee import BooleanField

from wtforms import widgets
from wtfpeewee.fields import BooleanSelectField
from wtfpeewee.fields import ModelSelectField
from wtfpeewee.orm import ModelConverter


class BaseModelConverter(ModelConverter):
    def __init__(self, *args, **kwargs):
        super(BaseModelConverter, self).__init__(*args, **kwargs)
        self.converters[BooleanField] = self.handle_boolean

    def handle_boolean(self, model, field, **kwargs):
        return field.name, BooleanSelectField(**kwargs)


class ChosenAjaxSelectWidget(widgets.Select):
    def __init__(self, data_source, data_param, *args, **kwargs):
        self.data_source = data_source
        self.data_param = data_param
        super(ChosenAjaxSelectWidget, self).__init__(*args, **kwargs)

    def __call__(self, field, **kwargs):
        if field.allow_blank and not self.multiple:
            kwargs['data-role'] = u'ajax-chosenblank'
        else:
            kwargs['data-role'] = u'ajax-chosen'
        kwargs['data-source'] = self.data_source
        kwargs['data-param'] = self.data_param
        kwargs['data-placeholder'] = 'Type to search...'

        return super(ChosenAjaxSelectWidget, self).__call__(field, **kwargs)


class LimitedModelSelectField(ModelSelectField):
    def iter_choices(self):
        for obj in self.query.limit(20):
            yield (obj._pk, self.get_label(obj), obj == self.data)
