from peewee import BooleanField

from wtforms import widgets
from wtfpeewee.fields import BooleanSelectField
from wtfpeewee.fields import ModelSelectField
from wtfpeewee.fields import wtf_choice
from wtfpeewee.orm import ModelConverter


class BaseModelConverter(ModelConverter):
    def __init__(self, *args, **kwargs):
        super(BaseModelConverter, self).__init__(*args, **kwargs)
        self.converters[BooleanField] = self.handle_boolean

    def handle_boolean(self, model, field, **kwargs):
        return field.name, BooleanSelectField(**kwargs)


class AjaxSelectWidget(widgets.Select):
    """
    Select whose options are (re)populated from the model admin's ajax_list
    endpoint by a search input -- see Admin.ajaxSelect in admin.js.
    """
    def __init__(self, data_source, data_param, *args, **kwargs):
        self.data_source = data_source
        self.data_param = data_param
        super(AjaxSelectWidget, self).__init__(*args, **kwargs)

    def __call__(self, field, **kwargs):
        kwargs['data-role'] = 'ajax-select'
        kwargs['data-source'] = self.data_source
        kwargs['data-param'] = self.data_param
        return super(AjaxSelectWidget, self).__call__(field, **kwargs)


#: Backwards-compatible alias from the chosen.js era.
ChosenAjaxSelectWidget = AjaxSelectWidget


class LimitedModelSelectField(ModelSelectField):
    limit = 20

    def iter_choices(self):
        found = False
        for obj in self.query.limit(self.limit):
            if obj == self.data:
                found = True
            yield wtf_choice(obj._pk, self.get_label(obj), obj == self.data)

        # ensure the selected object is present even when it falls outside
        # the first `limit` rows.
        if isinstance(self.data, self.model) and not found:
            yield wtf_choice(self.data._pk, self.get_label(self.data), True)
