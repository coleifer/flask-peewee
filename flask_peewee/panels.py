from flask_peewee.admin import AdminPanel


class RecentRowsPanel(AdminPanel):
    template_name = 'admin/panels/recent_rows.html'

    def __init__(self, admin, title, model, columns=None, limit=5,
                 order_by=None):
        super(RecentRowsPanel, self).__init__(admin, title)
        self.model = model
        self.columns = columns
        self.limit = limit
        self.order_by = order_by or model._meta.primary_key

    def edit_url(self, obj, user):
        model_admin = self.admin.get_admin_for(self.model)
        if model_admin and model_admin.check_edit(user):
            return self.admin.get_admin_url(obj)

    def get_context(self):
        # columns fall back to the model admin's, resolved here and not in
        # __init__ since register_panel may run before the admin is registered.
        model_admin = self.admin.get_admin_for(self.model)
        query = (self.admin.get_query_for(self.model)
                 .order_by(self.order_by.desc())
                 .limit(self.limit))
        return {
            'object_list': query,
            'columns': self.columns or (model_admin and model_admin.columns),
        }
