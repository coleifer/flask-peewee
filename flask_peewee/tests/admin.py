
import base64
import csv
import datetime
import io
import json
import re

from flask import g
from flask import get_flashed_messages
from flask import request
from flask import session
from flask import url_for

from flask_peewee.admin import AdminFilterModelConverter
from flask_peewee.admin import AdminPanel
from flask_peewee.admin import Export
from flask_peewee.admin import ModelAdmin
from flask_peewee.serializer import Serializer
from flask_peewee.filters import FilterForm
from flask_peewee.filters import FilterMapping
from flask_peewee.filters import FilterModelConverter
from flask_peewee.filters import make_field_tree
from flask_peewee.panels import RecentRowsPanel
from flask_peewee.utils import PaginatedQuery
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import AModel
from flask_peewee.tests.test_app import BDetails
from flask_peewee.tests.test_app import BModel
from flask_peewee.tests.test_app import CModel
from flask_peewee.tests.test_app import Comment
from flask_peewee.tests.test_app import DModel
from flask_peewee.tests.test_app import Entry
from flask_peewee.tests.test_app import Link
from flask_peewee.tests.test_app import Message
from flask_peewee.tests.test_app import Note
from flask_peewee.tests.test_app import Ping
from flask_peewee.tests.test_app import ScopedItem
from flask_peewee.tests.test_app import ScopedRef
from flask_peewee.tests.test_app import TSModel
from flask_peewee.tests.test_app import Tweet
from flask_peewee.tests.test_app import User
from flask_peewee.tests.test_app import admin
from flask_peewee.tests.test_app import auth
from flask_peewee.tests.test_app import db
from flask_peewee.utils import check_password
from flask_peewee.utils import get_next
from flask_peewee.utils import make_password

from peewee import BlobField
from peewee import CharField
from peewee import ForeignKeyField
from wtforms.fields import FieldList
from wtforms.fields import StringField
from wtfpeewee.orm import model_form


class BaseAdminTestCase(FlaskPeeweeTestCase):
    def login(self, context=None):
        context = context or self.app
        context.post('/accounts/login/', data={
            'username': 'admin',
            'password': 'admin',
        })

    def logout(self, context=None):
        context = context or self.app
        context.post('/accounts/logout/')

    def assertRedirect(self, resp):
        self.assertTrue(resp.status_code in (302, 303))


class AdminTestCase(BaseAdminTestCase):
    def test_admin_auth(self):
        self.create_users()

        # check login redirect
        resp = self.app.get('/admin/')
        self.assertRedirect(resp)
        self.assertTrue(resp.headers['location'].endswith((
            '/accounts/login/?next=%2Fadmin%2F',
            '/accounts/login/?next=/admin/')))

        # try logging in as a normal user, get a 403 forbidden
        resp = self.app.post('/accounts/login/', data={
            'username': 'normal',
            'password': 'normal',
            'next': '/admin/',
        })
        self.assertRedirect(resp)
        self.assertTrue(resp.headers['location'].endswith('/admin/'))

        resp = self.app.get('/admin/')
        self.assertEqual(resp.status_code, 403)

        # log out from normal user
        resp = self.app.get('/accounts/logout/')

        # try logging in as an admin and get a 200
        resp = self.app.post('/accounts/login/', data={
            'username': 'admin',
            'password': 'admin',
            'next': '/admin/',
        })
        self.assertRedirect(resp)
        self.assertTrue(resp.headers['location'].endswith('/admin/'))

        resp = self.app.get('/admin/')
        self.assertEqual(resp.status_code, 200)

    def test_url_resolution(self):
        # need to be in a 'request' context to use ``url_for``
        with self.flask_app.test_request_context('/'):
            # admin urls
            self.assertEqual(url_for('admin.index'), '/admin/')

            # modeladmin urls
            self.assertEqual(url_for('admin.user_index'), '/admin/user/')
            self.assertEqual(url_for('admin.user_add'), '/admin/user/add/')
            self.assertEqual(url_for('admin.user_edit', pk=1), '/admin/user/1/')
            self.assertEqual(url_for('admin.user_delete'), '/admin/user/delete/')

            # panel urls
            self.assertEqual(url_for('admin.panel_notes_create'), '/admin/notes/create/')

    def test_index_view(self):
        self.create_users()
        self.login()

        # check for context in the index view
        resp = self.app.get('/admin/')
        self.assertEqual(resp.status_code, 200)

        # check that we have the stuff from the auth module and the index view
        self.assertContext('user', self.admin)
        self.assertContext('model_admins', [
            admin._registry[AModel],
            admin._registry[BDetails],
            admin._registry[BModel],
            admin._registry[CModel],
            admin._registry[Comment],
            admin._registry[DModel],
            admin._registry[Entry],
            admin._registry[Message],
            admin._registry[Note],
            admin._registry[Ping],
            admin._registry[ScopedItem],
            admin._registry[ScopedRef],
            admin._registry[User],
        ])
        self.assertContext('panels', [
            admin._panels['Notes'],
            admin._panels['Recent messages'],
        ])

    def test_theme(self):
        self.create_users()
        self.login()

        # no theme by default, just the base stylesheet
        resp = self.app.get('/admin/')
        body = resp.data.decode('utf-8')
        self.assertTrue('css/admin.css' in body)
        self.assertFalse('css/admin-' in body)

        try:
            admin.theme = 'crisp'
            body = self.app.get('/admin/').data.decode('utf-8')
            self.assertTrue('css/admin.css' in body)
            self.assertTrue('css/admin-crisp.css' in body)

            admin.theme = 'plastic'
            body = self.app.get('/admin/').data.decode('utf-8')
            self.assertTrue('css/admin-plastic.css' in body)
        finally:
            admin.theme = None

    def test_model_admin_add(self):
        self.create_users()
        self.assertEqual(User.select().count(), 3)

        with self.flask_app.test_client() as c:
            self.login(c)

            # the add url returns a 200
            resp = c.get('/admin/user/add/')
            self.assertEqual(resp.status_code, 200)

            # ensure the user, model_admin and form are correct in the context
            self.assertContext('user', self.admin)
            self.assertContext('model_admin', admin._registry[User])

            self.assertTrue('form' in self.flask_app._template_context)
            frm = self.flask_app._template_context['form']
            self.assertEqual(sorted(frm._fields.keys()), [
                'active',
                'admin',
                'email',
                'join_date',
                'password',
                'username',
            ])

            # make an incomplete post and get a 200 with errors
            resp = c.post('/admin/user/add/', data={
                'username': '',
                'password': 'xxx',
                'active': '1',
                'email': '',
                'join_date': '2011-01-01 00:00:00',
            })
            self.assertEqual(resp.status_code, 200)

            # no new user created
            self.assertEqual(User.select().count(), 3)

            # check the form for errors
            frm = self.get_context('form')
            self.assertEqual(frm.errors, {
                'username': ['This field is required.'],
                'email': ['This field is required.'],
            })

            # make a complete post and get a 302 to the edit page
            resp = c.post('/admin/user/add/', data={
                'username': 'new',
                'password': 'new',
                'active': '1',
                'email': 'new@new.new',
                'join_date-date': '2011-01-01',
                'join_date-time': '00:00:00',
            })
            self.assertRedirect(resp)

            # new user was created
            self.assertEqual(User.select().count(), 4)

            # check they have the correct data on the new instance
            user = User.get(username='new')
            self.assertEqual(user.active, True)
            self.assertEqual(user.admin, False)
            self.assertEqual(user.email, 'new@new.new')
            self.assertEqual(user.join_date, datetime.datetime(2011, 1, 1))
            self.assertTrue(check_password('new', user.password))

            # check the redirect was correct
            self.assertTrue(resp.headers['location'].endswith('/admin/user/%d/' % user.id))

    def test_model_admin_edit(self):
        users = self.create_users()
        self.assertEqual(User.select().count(), 3)

        # grab an id so we can test a 404 on non-existent user
        unused_id = [x for x in range(1, 5) if not User.filter(id=x).exists()][0]

        with self.flask_app.test_client() as c:
            self.login(c)

            # nonexistant user 404s
            resp = c.get('/admin/user/%d/' % unused_id)
            self.assertEqual(resp.status_code, 404)

            # edit page returns a 200
            resp = c.get('/admin/user/%d/' % self.normal.id)
            self.assertEqual(resp.status_code, 200)

            # check the user, model_admin and form are correct in the context
            self.assertContext('user', self.admin)
            self.assertContext('model_admin', admin._registry[User])

            self.assertTrue('form' in self.flask_app._template_context)
            frm = self.flask_app._template_context['form']
            self.assertEqual(sorted(frm._fields.keys()), [
                'active',
                'admin',
                'email',
                'join_date',
                'password',
                'username',
            ])

            # check the form pulled the right data off the model
            self.assertEqual(frm.data, {
                'username': 'normal',
                'password': frm.password.data, # skip this
                'email': '',
                'admin': False,
                'active': True,
                'join_date': frm.join_date.data, # microseconds...bleh
            })

            # make an incomplete post to update the user and get a 200 w/errors
            resp = c.post('/admin/user/%d/' % self.normal.id, data={
                'username': '',
                'password': '',
                'active': '1',
                'email': 'fap@fap.fap',
                'join_date-date': '2011-01-01',
                'join_date-time': '00:00:00',
            })
            self.assertEqual(resp.status_code, 200)

            # no new user created
            self.assertEqual(User.select().count(), 3)

            # refresh database content
            normal = User.get(id=self.normal.id)
            self.assertEqual(normal.username, 'normal') # was not saved

            # check the form for errors
            frm = self.get_context('form')
            self.assertEqual(frm.errors, {
                'username': ['This field is required.'],
                'password': ['This field is required.'],
            })

            # make a complete post
            resp = c.post('/admin/user/%d/' % self.normal.id, data={
                'username': 'edited',
                'password': 'edited',
                'active': '1',
                'email': 'x@x.x',
                'join_date-date': '2011-01-01',
                'join_date-time': '00:00:00',
            })
            self.assertRedirect(resp)

            # no new user was created
            self.assertEqual(User.select().count(), 3)

            # grab from the database
            user = User.get(username='edited')
            self.assertEqual(user.id, self.normal.id) # it is the same user

            self.assertTrue(check_password('edited', user.password))
            self.assertEqual(user.active, True)
            self.assertEqual(user.admin, False)
            self.assertEqual(user.email, 'x@x.x')
            self.assertEqual(user.join_date, datetime.datetime(2011, 1, 1))

            self.assertTrue(resp.headers['location'].endswith('/admin/user/%d/' % user.id))

            # make another post without modifying the password, should stay same
            resp = c.post('/admin/user/%d/' % user.id, data={
                'username': 'edited2',
                'password': user.password,
                'active': '1',
                'email': 'x@x.x',
                'join_date-date': '2011-01-01',
                'join_date-time': '00:00:00',
            })
            self.assertRedirect(resp)

            # no new user was created
            self.assertEqual(User.select().count(), 3)

            # grab from the database
            user = User.get(username='edited2')
            self.assertEqual(user.id, self.normal.id) # it is the same user

            # the password has not changed
            self.assertTrue(check_password('edited', user.password))

    def test_model_admin_delete(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            self.login(c)

            # do a basic get, nothing much going on
            resp = c.get('/admin/user/delete/')
            self.assertEqual(resp.status_code, 200)

            self.assertContext('user', self.admin)
            self.assertContext('model_admin', admin._registry[User])

            query = self.get_context('query')
            self.assertEqual(list(query), [])

            # send it a single id
            resp = c.get('/admin/user/delete/?id=%d' % (self.normal.id))
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query), [self.normal])

            # ensure nothing was deleted
            self.assertEqual(User.select().count(), 3)

            # post to it, get a redirect on success
            resp = c.post('/admin/user/delete/', data={'id': self.normal.id})
            self.assertRedirect(resp)

            # ensure the user was deleted
            self.assertEqual(User.select().count(), 2)
            self.assertRaises(User.DoesNotExist, User.get, id=self.normal.id)

            self.assertTrue(resp.headers['location'].endswith('/admin/user/'))

            # do a multi-delete
            resp = c.get('/admin/user/delete/?id=%d&id=%d' % (self.admin.id, self.inactive.id))
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query), [self.admin, self.inactive])

            # post to it and check both deleted
            resp = c.post('/admin/user/delete/', data={'id': [self.admin.id, self.inactive.id]})
            self.assertRedirect(resp)

            self.assertEqual(User.select().count(), 0)

    def test_model_admin_recursive_delete(self):
        self.create_users()

        m1 = Message.create(user=self.normal, content='test1')
        m2 = Message.create(user=self.normal, content='test2')
        m3 = Message.create(user=self.admin, content='test3')

        n1 = Note.create(user=self.normal, message='test1')
        n2 = Note.create(user=self.normal, message='test2')
        n3 = Note.create(user=self.admin, message='test3')

        a1 = AModel.create(a_field='a1')
        a2 = AModel.create(a_field='a2')
        b1 = BModel.create(b_field='b1', a=a1)
        b2 = BModel.create(b_field='b2', a=a2)
        bd1= BDetails.create(b=b1)
        bd2= BDetails.create(b=b2)
        c1 = CModel.create(c_field='c1', b=b1)
        c2 = CModel.create(c_field='c2', b=b2)
        d1 = DModel.create(d_field='d1', c=c1)
        d2 = DModel.create(d_field='d2', c=c2)

        with self.flask_app.test_client() as c:
            self.login(c)

            resp = c.get('/admin/amodel/delete/?id=%d' % (a1.id))
            self.assertEqual(resp.status_code, 200)

            collected = self.get_context('collected')
            self.assertEqual(collected, {
                a1.id: [
                    (0, BDetails, [bd1]),
                    (0, BModel, [b1]),
                    (0, CModel, [c1]),
                    (0, DModel, [d1]),
                ]
            })

            resp = c.post('/admin/amodel/delete/', data={'id': a1.id})
            self.assertRedirect(resp)
            self.assertEqual(AModel.select().count(), 1)
            self.assertEqual(BModel.select().count(), 1)
            self.assertEqual(BDetails.select().count(), 1)
            self.assertEqual(CModel.select().count(), 1)
            self.assertEqual(DModel.select().count(), 1)

            # send it a single id
            resp = c.get('/admin/user/delete/?id=%d' % (self.normal.id))
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query), [self.normal])

            collected = self.get_context('collected')
            self.assertEqual(len(collected), 1)
            u_k = collected[self.normal.id]
            self.assertEqual(len(u_k), 2)

            self.assertEqual(u_k, [
                (0, Message, [m1, m2]),
                (0, Note, [n1, n2]),
            ])

            # post to it, get a redirect on success
            resp = c.post('/admin/user/delete/', data={'id': self.normal.id})
            self.assertRedirect(resp)

            self.assertEqual(User.select().count(), 2)
            self.assertEqual(Message.select().count(), 1)
            self.assertEqual(Note.select().count(), 1)

            resp = c.get('/admin/user/delete/?id=%d&id=%d' % (self.admin.id, self.inactive.id))
            self.assertEqual(resp.status_code, 200)

            collected = self.get_context('collected')

            self.assertEqual(len(collected), 2)
            u_k = collected[self.admin.id]
            self.assertEqual(len(u_k), 2)

            self.assertEqual(u_k, [
                (0, Message, [m3]),
                (0, Note, [n3]),
            ])

            u_k = collected[self.inactive.id]
            self.assertEqual(len(u_k), 0)

            # post to it, get a redirect on success
            resp = c.post('/admin/user/delete/', data={'id': [self.admin.id, self.inactive.id]})
            self.assertRedirect(resp)

            self.assertEqual(User.select().count(), 0)
            self.assertEqual(Message.select().count(), 0)
            self.assertEqual(Note.select().count(), 0)

    def test_delete_respects_get_query(self):
        # ScopedItemAdmin.get_query() hides rows flagged hidden. Both the GET
        # confirmation and the POST go through it, so a hidden row can be
        # neither disclosed nor deleted.
        self.create_users()
        visible = ScopedItem.create(label='visible')
        hidden = ScopedItem.create(label='hidden', hidden=True)

        with self.flask_app.test_client() as c:
            self.login(c)

            # the confirmation page for a hidden row shows nothing.
            resp = c.get('/admin/scopeditem/delete/?id=%d' % hidden.id)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(list(self.get_context('query')), [])

            # posting the hidden id deletes nothing.
            resp = c.post('/admin/scopeditem/delete/', data={'id': hidden.id})
            self.assertRedirect(resp)
            self.assertTrue(
                ScopedItem.select().where(ScopedItem.id == hidden.id).exists())

            # a visible row is still shown and deletable.
            resp = c.get('/admin/scopeditem/delete/?id=%d' % visible.id)
            self.assertEqual(list(self.get_context('query')), [visible])
            resp = c.post('/admin/scopeditem/delete/', data={'id': visible.id})
            self.assertRedirect(resp)
            self.assertFalse(
                ScopedItem.select().where(ScopedItem.id == visible.id).exists())

    def create_notes(self):
        self.create_users()
        return (Note.create(user=self.normal, message='Alpha'),
                Note.create(user=self.normal, message='Beta'))

    def test_action_confirm(self):
        n1, n2 = self.create_notes()

        with self.flask_app.test_client() as c:
            self.login(c)

            # the empty check precedes the confirmation redirect.
            c.post('/admin/note/', data={'action': 'Lower'})
            self.assertTrue('Please select one or more rows.' in
                            get_flashed_messages())

            # a plain action runs straight from the index post.
            resp = c.post('/admin/note/', data={'action': 'Upper',
                                                'id': [n1.id]})
            self.assertRedirect(resp)
            self.assertTrue(resp.headers['location'].endswith('/admin/note/'))
            self.assertEqual(Note.get(Note.id == n1.id).message, 'ALPHA')
            self.assertEqual(Note.get(Note.id == n2.id).message, 'Beta')

            # an unrecognized name on the confirm url 404s, as does a
            # non-confirm action.
            resp = c.get('/admin/note/action/?name=Missing&id=%d' % n1.id)
            self.assertEqual(resp.status_code, 404)
            resp = c.get('/admin/note/action/?name=Upper&id=%d' % n1.id)
            self.assertEqual(resp.status_code, 404)

            # a confirm action redirects to the confirmation page instead.
            resp = c.post('/admin/note/', data={'action': 'Lower',
                                                'id': [n1.id, n2.id]})
            self.assertRedirect(resp)
            location = resp.headers['location']
            self.assertTrue('/admin/note/action/?name=Lower' in location)

            # nothing has run yet.
            self.assertEqual(Note.get(Note.id == n1.id).message, 'ALPHA')

            # the confirmation page lists the selected rows.
            resp = c.get(location)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(list(self.get_context('query')), [n1, n2])

            # posting runs the callback and redirects to the index.
            resp = c.post('/admin/note/action/', data={
                'name': 'Lower', 'id': [n1.id, n2.id]})
            self.assertRedirect(resp)
            self.assertEqual(get_flashed_messages(),
                             ['Successfully applied Lower to 2 Notes'])
            self.assertEqual(Note.get(Note.id == n1.id).message, 'alpha')
            self.assertEqual(Note.get(Note.id == n2.id).message, 'beta')

            # a callback returning a Response is passed through.
            resp = c.post('/admin/note/action/', data={
                'name': 'Download', 'id': [n1.id]})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data.decode('utf8'), str(n1.id))

    def test_action_respects_get_query(self):
        self.create_users()
        hidden = ScopedItem.create(label='hidden', hidden=True)
        v1 = ScopedItem.create(label='visible')
        v2 = ScopedItem.create(label='visible')

        with self.flask_app.test_client() as c:
            self.login(c)

            # the confirmation post marks only the visible row.
            resp = c.post('/admin/scopeditem/action/', data={
                'name': 'Mark', 'id': [v1.id, hidden.id]})
            self.assertRedirect(resp)

            # so does the immediate path.
            resp = c.post('/admin/scopeditem/', data={
                'action': 'MarkNow', 'id': [v2.id, hidden.id]})
            self.assertRedirect(resp)

        self.assertEqual([i.label for i in
                          ScopedItem.select().order_by(ScopedItem.id)],
                         ['hidden', 'marked', 'marked'])

    def test_action_form(self):
        n1, n2 = self.create_notes()

        with self.flask_app.test_client() as c:
            self.login(c)

            # a form_class action implies confirmation.
            resp = c.post('/admin/note/', data={'action': 'Prefix',
                                                'id': [n1.id]})
            self.assertRedirect(resp)

            # a missing prefix re-renders with errors and runs nothing.
            resp = c.post('/admin/note/action/', data={
                'name': 'Prefix', 'id': [n1.id], 'prefix': ''})
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(self.get_context('form').errors)
            self.assertEqual(list(self.get_context('query')), [n1])
            self.assertEqual(Note.get(Note.id == n1.id).message, 'Alpha')

            # a valid post reaches the callback with the form value.
            resp = c.post('/admin/note/action/', data={
                'name': 'Prefix', 'id': [n1.id], 'prefix': 'x-'})
            self.assertRedirect(resp)
            self.assertEqual(Note.get(Note.id == n1.id).message, 'x-Alpha')
            self.assertEqual(Note.get(Note.id == n2.id).message, 'Beta')

    def test_ajax_list_respects_related_get_query(self):
        # the FK picker on ScopedRef.item enumerates ScopedItem through its
        # admin's get_query(), so it cannot disclose hidden rows.
        self.create_users()
        visible = ScopedItem.create(label='visible')
        hidden = ScopedItem.create(label='hidden', hidden=True)

        with self.flask_app.test_client() as c:
            self.login(c)

            resp = c.get('/admin/scopedref/_ajax/?field=item')
            self.assertEqual(resp.status_code, 200)
            ids = [o['id'] for o in
                   json.loads(resp.data.decode('utf8'))['object_list']]
            self.assertIn(visible.id, ids)
            self.assertNotIn(hidden.id, ids)

            # searching for the hidden row returns nothing.
            resp = c.get('/admin/scopedref/_ajax/?field=item&query=hidden')
            data = json.loads(resp.data.decode('utf8'))
            self.assertEqual(data['object_list'], [])

    def test_fk_select_respects_related_get_query(self):
        # the non-ajax FK pickers (edit-form select, filter-form select) draw
        # candidates from the related admin's get_query(), so a scoped-out row
        # is never offered. the ajax picker is covered above.
        ScopedItem.create(label='visible')
        ScopedItem.create(label='hidden', hidden=True)

        class PlainRefAdmin(ModelAdmin):
            pass  # no foreign_key_lookups -> plain <select>, not ajax

        ref_admin = PlainRefAdmin(admin, ScopedRef)
        item_fk = ScopedRef._meta.fields['item']

        with self.flask_app.test_request_context():
            # edit-form select: bind the form and read the field's query.
            add_form = ref_admin.get_add_form()()
            edit_labels = [o.label for o in add_form.item.query]

            # filter-form select: the converter carries the scoped query.
            _, filter_field = AdminFilterModelConverter(ref_admin) \
                .handle_foreign_key(ScopedRef, item_fk)
            filter_labels = [o.label for o in filter_field.kwargs['query']]

        for labels in (edit_labels, filter_labels):
            self.assertIn('visible', labels)
            self.assertNotIn('hidden', labels)

    def test_ajax_list_bad_field_returns_empty(self):
        # the /_ajax/ route exists on every admin, so it must not 500 on inputs
        # it accepts: no field, a real fk the admin did not configure for
        # lookup, or a name that is not a field at all.
        self.create_users()

        with self.flask_app.test_client() as c:
            self.login(c)

            # NoteAdmin has no foreign_key_lookups configured.
            for url in ('/admin/note/_ajax/',
                        '/admin/note/_ajax/?field=user',
                        '/admin/note/_ajax/?field=nope'):
                resp = c.get(url)
                self.assertEqual(resp.status_code, 200, url)
                self.assertEqual(json.loads(resp.data)['object_list'], [], url)

    def test_form_field_args(self):
        # field_args threads through to wtf-peewee's model_form, so labels
        # and validators can be declared without overriding get_form().
        from werkzeug.datastructures import MultiDict
        from wtforms.validators import Length

        class AAdmin(ModelAdmin):
            field_args = {'a_field': {'label': 'The A',
                                      'validators': [Length(min=5)]}}

        a_admin = AAdmin(admin, AModel)
        Form = a_admin.get_form()

        form = Form(MultiDict({'a_field': 'abc'}))
        self.assertEqual(form.a_field.label.text, 'The A')
        self.assertFalse(form.validate())

        form = Form(MultiDict({'a_field': 'abcdef'}))
        self.assertTrue(form.validate())

    def test_model_admin_index(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            self.login(c)

            resp = c.get('/admin/user/?ordering=username')
            self.assertEqual(resp.status_code, 200)

            self.assertContext('user', self.admin)
            self.assertContext('model_admin', admin._registry[User])
            self.assertContext('ordering', 'username')

            active_filters = self.get_context('active_filters')
            self.assertEqual(active_filters, [])

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), [
                self.admin,
                self.inactive,
                self.normal,
            ])

            self.assertEqual(query.get_page(), 1)
            self.assertEqual(query.get_pages(), 1)

    def test_model_admin_index_filters(self):
        users = self.create_users()
        notes = {}

        for user in users:
            notes[user] = [Note.create(user=user, message='test-%d' % i) for i in range(3)]

        norm2 = self.create_user('normal2', 'normal2')

        with self.flask_app.test_client() as c:
            self.login(c)

            # test a simple lookup
            resp = c.get('/admin/user/?fo_username=0&fv_username=admin')
            self.assertEqual(resp.status_code, 200)

            self.assertContext('user', self.admin)
            self.assertContext('model_admin', admin._registry[User])
            self.assertContext('ordering', '')

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), [
                self.admin,
            ])

            # test a lookup using multiple values joined with "eq"
            resp = c.get('/admin/user/?fo_username=0&fv_username=admin&fo_username=0&fv_username=normal&ordering=-username')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), [
                self.normal,
                self.admin,
            ])

            # test a lookup using partial string (startswith)
            resp = c.get('/admin/user/?fo_username=2&fv_username=norm&ordering=-username')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), [
                norm2,
                self.normal,
            ])

            # test a lookup spanning a relation
            resp = c.get('/admin/note/?fo_user=0&fv_user=%d' % self.normal.id)
            self.assertEqual(resp.status_code, 200)

            self.assertContext('model_admin', admin._registry[Note])

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), notes[self.normal])

            # test a multi-value lookup spanning a relation
            resp = c.get('/admin/note/?fo_user=0&fv_user=%d&fo_user=0&fv_user=%d' % (self.normal.id, self.admin.id))
            self.assertEqual(resp.status_code, 200)

            self.assertContext('model_admin', admin._registry[Note])

            query = self.get_context('query')
            expected_notes = notes[self.admin] + notes[self.normal]
            self.assertEqual(list(query.get_list()), expected_notes)

            # named operations, equivalent to the positional lookups above
            resp = c.get('/admin/user/?fo_username=eq&fv_username=admin')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), [self.admin])

            resp = c.get('/admin/user/?fo_username=startswith&fv_username=norm&ordering=-username')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), [norm2, self.normal])

            active_filters = self.get_context('active_filters')
            self.assertEqual(len(active_filters), 1)
            self.assertEqual(active_filters[0]['key'], 'startswith')
            self.assertEqual(active_filters[0]['value'], 'norm')
            self.assertEqual(active_filters[0]['label'], 'username')

            resp = c.get('/admin/user/?fo_join_date=within_days&fv_join_date=1&ordering=username')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(query.get_list().count(), 4)

            # unknown operations and un-coercible values are ignored
            resp = c.get('/admin/user/?fo_username=bogus&fv_username=admin&ordering=username')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(query.get_list().count(), 4)

            resp = c.get('/admin/user/?fo_join_date=within_days&fv_join_date=xyz&ordering=username')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(query.get_list().count(), 4)

            resp = c.get('/admin/note/?fo_user=eq&fv_user=not-a-pk')
            self.assertEqual(resp.status_code, 200)

            # two different operations on one field are AND'd together, e.g.
            # a range, while repeated uses of one operation are OR'd.
            resp = c.get('/admin/user/?fo_id=gt&fv_id=%s&fo_id=lt&fv_id=%s&ordering=id' % (
                self.admin.id, norm2.id))
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), [self.normal, self.inactive])

            resp = c.get('/admin/user/?fo_id=eq&fv_id=%s&fo_id=eq&fv_id=%s&fo_id=gt&fv_id=%s&ordering=id' % (
                self.admin.id, self.normal.id, self.admin.id))
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), [self.normal])

    def test_model_admin_index_filter_rendering(self):
        self.create_users()
        for user in (self.admin, self.normal, self.inactive):
            Note.create(user=user, message='note-%s' % user.username)

        with self.flask_app.test_client() as c:
            self.login(c)

            def assert_selected(html, value):
                options = re.findall(r'<option[^>]*\bselected\b[^>]*>', html)
                self.assertEqual(len(options), 1)
                self.assertTrue('value="%s"' % value in options[0])

            # each row renders with its own operation and value, even when
            # several filters reference the same field.
            resp = c.get('/admin/user/?fo_username=startswith&fv_username=no&'
                         'fo_username=contains&fv_username=mal')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), [self.normal])

            active_filters = self.get_context('active_filters')
            self.assertEqual([(f['key'], f['value']) for f in active_filters], [
                ('startswith', 'no'),
                ('contains', 'mal')])

            for f in active_filters:
                assert_selected(f['op_field'](), f['key'])
                self.assertTrue('value="%s"' % f['value'] in f['value_field']())

            # select-type value fields (e.g. foreign keys) also render with
            # their own row's value selected.
            resp = c.get('/admin/note/?fo_user=eq&fv_user=%s&fo_user=eq&fv_user=%s' % (
                self.admin.id, self.inactive.id))
            self.assertEqual(resp.status_code, 200)

            active_filters = self.get_context('active_filters')
            self.assertEqual(len(active_filters), 2)
            for f in active_filters:
                assert_selected(f['op_field'](), 'eq')
                assert_selected(f['value_field'](), f['value'])

    def test_export(self):
        users = self.create_users()
        for user in users:
            Note.create(user=user, message='note-%s' % user.username)

        with self.flask_app.test_client() as c:
            self.login(c)

            resp = c.post('/admin/user/export/', data={
                'fields': ['username', 'email']})
            self.assertEqual(resp.status_code, 200)

            data = json.loads(resp.data)
            self.assertEqual(len(data), 3)
            for row in data:
                self.assertEqual(sorted(row), ['email', 'username'])
            self.assertEqual(
                sorted(row['username'] for row in data),
                ['admin', 'inactive', 'normal'])

            # exporting fields spanning a relation.
            resp = c.post('/admin/note/export/', data={
                'fields': ['message', 'user', 'user__username']})
            self.assertEqual(resp.status_code, 200)

            data = json.loads(resp.data)
            self.assertEqual(len(data), 3)
            for row in data:
                self.assertEqual(sorted(row), ['message', 'user'])
                self.assertEqual(list(row['user']), ['username'])
                self.assertEqual(row['message'], 'note-%s' % row['user']['username'])

            # exported records respect filters in the query-string.
            resp = c.post('/admin/user/export/?fo_username=eq&fv_username=admin',
                          data={'fields': ['username']})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(json.loads(resp.data), [{'username': 'admin'}])

    def test_export_streams_without_count(self):
        # the stream places separators with a first-row flag, not a pre-count,
        # so it issues no COUNT and cannot emit a stale comma when the row set
        # changes mid-iteration.
        import logging
        users = self.create_users()
        for user in users:
            Note.create(user=user, message='note-%s' % user.username)

        counts = []
        class H(logging.Handler):
            def emit(self, record):
                if 'COUNT(' in record.getMessage().upper():
                    counts.append(record.getMessage())
        logger = logging.getLogger('peewee')
        level, handler = logger.level, H()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        try:
            with self.flask_app.test_client() as c:
                self.login(c)
                resp = c.post('/admin/note/export/', data={'fields': ['message']})
                data = json.loads(resp.data)

                # an empty result set still streams valid JSON.
                empty = c.post('/admin/note/export/?fo_id=eq&fv_id=0',
                               data={'fields': ['id']})
                empty_data = json.loads(empty.data)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(level)

        self.assertEqual(len(data), 3)
        self.assertEqual(empty_data, [])
        self.assertEqual(counts, [])
        self.assertEqual(resp.mimetype, 'application/json')

    def test_export_excludes_sensitive_fields(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            self.login(c)

            # the password field is export_exclude'd, so it isn't offered...
            resp = c.get('/admin/user/export/')
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn(b'value="password"', resp.data)
            self.assertIn(b'value="username"', resp.data)

            # ...and can't be dumped by posting the field name directly.
            resp = c.post('/admin/user/export/', data={
                'fields': ['username', 'password']})
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertTrue(data)
            for row in data:
                self.assertEqual(list(row), ['username'])

    def test_export_no_fields_returns_ids_only(self):
        # an empty or fully-excluded selection must not fall through to a
        # full-row dump. it exports the primary key only, so export_exclude'd
        # columns such as the password hash never leak.
        self.create_users()
        pk = User._meta.primary_key.name

        with self.flask_app.test_client() as c:
            self.login(c)

            # no 'fields' posted at all.
            resp = c.post('/admin/user/export/')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertEqual(len(data), 3)
            for row in data:
                self.assertEqual(list(row), [pk])

            # only an excluded field posted, so nothing survives the allowlist.
            resp = c.post('/admin/user/export/', data={'fields': ['password']})
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertEqual(len(data), 3)
            for row in data:
                self.assertEqual(list(row), [pk])
                self.assertNotIn('password', row)

    def parse_csv(self, data):
        return list(csv.reader(io.StringIO(data.decode('utf-8'))))

    def test_export_csv(self):
        users = self.create_users()
        dt = datetime.datetime(2020, 1, 2, 3, 4, 5)
        for user in users:
            Note.create(user=user, message='note-%s' % user.username,
                        created_date=dt)

        with self.flask_app.test_client() as c:
            self.login(c)

            resp = c.post('/admin/note/export/', data={
                'fields': ['message', 'user__username', 'created_date'],
                'format': 'csv'})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.mimetype, 'text/csv')
            # plain utf-8, no BOM before the header.
            self.assertTrue(resp.data.startswith(b'message,'))

            rows = self.parse_csv(resp.data)
            self.assertEqual(rows[0], ['message', 'user__username', 'created_date'])
            self.assertEqual(sorted(r[1] for r in rows[1:]),
                             ['admin', 'inactive', 'normal'])
            for row in rows[1:]:
                self.assertEqual(row[0], 'note-%s' % row[1])

            # datetimes are the same strings the json export produces.
            resp = c.post('/admin/note/export/', data={
                'fields': ['created_date'], 'format': 'json'})
            self.assertEqual(
                [r[2] for r in rows[1:]],
                [r['created_date'] for r in json.loads(resp.data)])

            # commas, quotes and newlines survive a round-trip. ?id= limits
            # the rows.
            tricky = 'a "quoted" bit, a comma\nand a newline'
            note = Note.create(user=users[0], message=tricky)
            resp = c.post('/admin/note/export/?id=%s' % note.id, data={
                'fields': ['message'], 'format': 'csv'})
            self.assertEqual(self.parse_csv(resp.data), [['message'], [tricky]])

    def test_export_csv_none_empty(self):
        self.create_users()
        Link.create(src=self.admin, dst=self.normal, label='ab')
        Link.create(src=self.admin, dst=None, label='a-null')

        related = LinkAdmin(admin, Link).collect_related_fields(Link, {}, [])

        def export_rows(fields):
            export = Export(Link.select().order_by(Link.id), related, fields)
            return self.parse_csv(b''.join(export.csv_response().response))

        self.assertEqual(export_rows(['label', 'dst']), [
            ['label', 'dst'],
            ['ab', str(self.normal.id)],
            ['a-null', '']])

        # the null-dst row drops on the inner join, as in the json export.
        self.assertEqual(export_rows(['label', 'dst', 'dst__username']), [
            ['label', 'dst', 'dst__username'],
            ['ab', '', 'normal']])

    def test_export_csv_binary(self):
        # binary columns take the serializer's base64 conversion, same as json.
        class Blobby(db.Model):
            data = BlobField()

        db.database.create_tables([Blobby])
        try:
            payload = b'\x00\xffbytes\n'
            Blobby.create(data=payload)
            export = Export(Blobby.select(), {}, ['data'])
            rows = self.parse_csv(b''.join(export.csv_response().response))
            self.assertEqual(rows, [
                ['data'],
                [base64.b64encode(payload).decode('ascii')]])
        finally:
            db.database.drop_tables([Blobby])

    def test_admin_search(self):
        users = self.create_users()
        for user in users:
            self.create_message(user, 'msg from %s' % user.username)

        with self.flask_app.test_client() as c:
            self.login(c)

            # search on a direct field (content)
            resp = c.get('/admin/message/?q=from+admin')
            self.assertEqual(resp.status_code, 200)
            results = list(self.get_context('query').get_list())
            self.assertEqual([m.content for m in results], ['msg from admin'])

            # search traversing a foreign key (user__username), case-insensitive
            resp = c.get('/admin/message/?q=NORMAL')
            self.assertEqual(resp.status_code, 200)
            results = list(self.get_context('query').get_list())
            self.assertEqual([m.user.username for m in results], ['normal'])

            # empty search returns everything
            resp = c.get('/admin/message/?q=')
            results = list(self.get_context('query').get_list())
            self.assertEqual(len(results), 3)

    def test_pagination_page_range(self):
        user = self.create_user('paginate', 'paginate')

        # an empty result set has no pages, so no page numbers to render.
        with self.flask_app.test_request_context('/?page=1'):
            pq = PaginatedQuery(Note.select(), 20)
            self.assertEqual(pq.get_pages(), 0)
            self.assertEqual(pq.get_page_range(), [])

        for i in range(95):
            Note.create(user=user, message='n%d' % i)

        # 95 notes / 20 per page = 5 pages; window around the current page.
        with self.flask_app.test_request_context('/?page=1'):
            pq = PaginatedQuery(Note.select(), 20)
            self.assertEqual(pq.get_count(), 95)
            self.assertEqual(pq.get_pages(), 5)
            self.assertEqual(pq.get_page_range(), [1, 2, 3, 4, 5])

        for i in range(300):
            Note.create(user=user, message='m%d' % i)

        # 395 notes -> 20 pages; middle page shows ellipsis gaps on both sides.
        with self.flask_app.test_request_context('/?page=10'):
            pq = PaginatedQuery(Note.select(), 20)
            self.assertEqual(pq.get_pages(), 20)
            self.assertEqual(pq.get_page_range(),
                             [1, None, 7, 8, 9, 10, 11, 12, 13, None, 20])

    def test_model_admin_index_pagination(self):
        users = self.create_users()
        notes = {}

        for user in users:
            notes[user] = [Note.create(user=user, message='test-%d' % i) for i in range(20)]

        with self.flask_app.test_client() as c:
            self.login(c)

            # test a simple lookup
            resp = c.get('/admin/note/?ordering=id')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), notes[users[0]])

            resp = c.get('/admin/note/?ordering=id&page=2')
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), notes[users[1]])

            resp = c.get('/admin/note/?ordering=id&page=1&fo_user=0&fv_user=%d&fo_user=0&fv_user=%d' % (users[1].id, users[2].id))
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), notes[users[1]])

            resp = c.get('/admin/note/?ordering=id&page=2&fo_user=0&fv_user=%d&fo_user=0&fv_user=%d' % (users[1].id, users[2].id))
            self.assertEqual(resp.status_code, 200)

            query = self.get_context('query')
            self.assertEqual(list(query.get_list()), notes[users[2]])

    def test_index_pagination_count_free(self):
        import logging
        self.create_users()
        for i in range(20):
            Note.create(user=self.admin, message='n%02d' % i)

        counts = []
        class H(logging.Handler):
            def emit(self, record):
                if 'COUNT(' in record.getMessage().upper():
                    counts.append(record.getMessage())
        logger = logging.getLogger('peewee')
        level, handler = logger.level, H()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        note_admin = admin._registry[Note]
        note_admin.paginate_count = False
        try:
            with self.flask_app.test_client() as c:
                self.login(c)

                # exactly one full page renders no pagination controls.
                resp = c.get('/admin/note/?ordering=id')
                self.assertEqual(resp.status_code, 200)
                query = self.get_context('query')
                self.assertEqual(len(query.get_list()), 20)
                self.assertFalse(query.has_next)
                self.assertNotIn(b'page-link', resp.data)
                self.assertNotIn(b' record', resp.data)

                extra = Note.create(user=self.admin, message='n20')

                # first page: disabled prev, live next, no numbered links.
                resp = c.get('/admin/note/?ordering=id')
                query = self.get_context('query')
                self.assertEqual(len(query.get_list()), 20)
                self.assertTrue(query.has_next)
                self.assertEqual(resp.data.count(b'page-link'), 2)
                self.assertIn(b'<span class="page-link">Previous</span>', resp.data)
                self.assertIn(b'page=2">Next</a>', resp.data)
                self.assertNotIn(b' record', resp.data)

                # last page: live prev, disabled next.
                resp = c.get('/admin/note/?ordering=id&page=2')
                query = self.get_context('query')
                self.assertEqual(query.get_list(), [extra])
                self.assertFalse(query.has_next)
                self.assertEqual(resp.data.count(b'page-link'), 2)
                self.assertIn(b'page=1">Previous</a>', resp.data)
                self.assertIn(b'<span class="page-link">Next</span>', resp.data)
        finally:
            del note_admin.paginate_count
            logger.removeHandler(handler)
            logger.setLevel(level)

        # no COUNT(*) was issued by any of the count-free index views.
        self.assertEqual(counts, [])

    def test_paginate_count_suppresses_counts(self):
        self.create_users()
        Note.create(user=self.admin, message='n0')

        def dashboard_count(data, name):
            pattern = (r'href="/admin/%s/">%s</a></td>\s*'
                       r'<td class="records[^>]*>(\d*)</td>') % (name, name.title())
            return re.search(pattern.encode('utf8'), data).groups()[0]

        with self.flask_app.test_client() as c:
            self.login(c)

            # counts show by default.
            resp = c.get('/admin/note/')
            self.assertIn(b'Note (1)', resp.data)
            resp = c.get('/admin/')
            self.assertEqual(dashboard_count(resp.data, 'note'), b'1')

            note_admin = admin._registry[Note]
            note_admin.paginate_count = False
            try:
                # tab count suppressed on the model views.
                resp = c.get('/admin/note/')
                self.assertNotIn(b'Note (', resp.data)

                # dashboard cell empty for this model, others unaffected.
                resp = c.get('/admin/')
                self.assertEqual(dashboard_count(resp.data, 'note'), b'')
                self.assertEqual(dashboard_count(resp.data, 'user'), b'3')
            finally:
                del note_admin.paginate_count

    def test_panel_simple(self):
        users = self.create_users()

        with self.flask_app.test_client() as c:
            self.login(c)

            self.assertEqual(Note.select().count(), 0)

            resp = c.post('/admin/notes/create/', data={'message': 'testing'})
            self.assertRedirect(resp)
            self.assertTrue(resp.headers['location'].endswith('/admin/'))

            self.assertEqual(Note.select().count(), 1)

            note = Note.get(user=self.admin)
            self.assertEqual(note.message, 'testing')


class AdminFieldsetTestCase(BaseAdminTestCase):
    def setUp(self):
        super(AdminFieldsetTestCase, self).setUp()
        db.database.drop_tables([Entry])
        db.database.create_tables([Entry])

    def create_entry(self):
        return Entry.create(title='t1', body='b1',
                            created=datetime.datetime(2024, 1, 2, 3, 4, 5))

    def test_readonly_edit_and_add(self):
        self.create_users()
        entry = self.create_entry()
        entry_admin = admin._registry[Entry]

        # readonly_fields alone, without fieldsets.
        entry_admin.fieldsets = None
        try:
            with self.flask_app.test_client() as c:
                self.login(c)

                # edit renders an inert value row instead of an input.
                body = c.get('/admin/entry/%d/' % entry.id).data.decode('utf-8')
                self.assertTrue('form-control-plaintext' in body)
                self.assertTrue('Created' in body)
                self.assertTrue('2024-01-02 03:04:05' in body)
                self.assertTrue('name="created' not in body)

                frm = self.get_context('form')
                self.assertEqual(sorted(frm._fields), ['body', 'status', 'title'])

                # the readonly row keeps its model-field position, after status.
                self.assertTrue(body.index('name="status"') <
                                body.index('form-control-plaintext'))

                # add omits the readonly field entirely.
                body = c.get('/admin/entry/add/').data.decode('utf-8')
                self.assertTrue('form-control-plaintext' not in body)
                self.assertTrue('Created' not in body)
                self.assertTrue('name="created' not in body)
        finally:
            del entry_admin.fieldsets

    def test_readonly_not_posted(self):
        self.create_users()
        entry = self.create_entry()

        with self.flask_app.test_client() as c:
            self.login(c)

            # a crafted post naming the readonly column does not change it.
            resp = c.post('/admin/entry/%d/' % entry.id, data={
                'title': 'edited',
                'body': 'b2',
                'status': 'live',
                'created': '2030-12-31 23:59:59',
                'created-date': '2030-12-31',
                'created-time': '23:59:59',
            })
            self.assertRedirect(resp)

            obj = Entry.get(Entry.id == entry.id)
            self.assertEqual(obj.title, 'edited')
            self.assertEqual(obj.created, datetime.datetime(2024, 1, 2, 3, 4, 5))

            # same on add, the column falls back to its default.
            resp = c.post('/admin/entry/add/', data={
                'title': 't2',
                'body': '',
                'status': 'draft',
                'created-date': '2030-12-31',
                'created-time': '23:59:59',
            })
            self.assertRedirect(resp)
            obj = Entry.get(Entry.title == 't2')
            self.assertNotEqual(obj.created, datetime.datetime(2030, 12, 31, 23, 59, 59))

    def test_fieldsets_render(self):
        self.create_users()
        entry = self.create_entry()

        with self.flask_app.test_client() as c:
            self.login(c)
            body = c.get('/admin/entry/%d/' % entry.id).data.decode('utf-8')

            # sections in order: Content legend, its fields, the collapsed
            # Meta details holding the inert readonly row, then the unlisted
            # field in a trailing unlabeled section.
            positions = [
                body.index('<legend>Content</legend>'),
                body.index('name="title"'),
                body.index('name="body"'),
                body.index('<details class="mb-3">'),
                body.index('Meta</summary>'),
                body.index('form-control-plaintext'),
                body.index('2024-01-02 03:04:05'),
                body.index('</details>'),
                body.index('name="status"'),
            ]
            self.assertEqual(positions, sorted(positions))
            self.assertTrue('name="created' not in body)

            # add keeps the sections but skips the readonly row.
            body = c.get('/admin/entry/add/').data.decode('utf-8')
            self.assertTrue('<legend>Content</legend>' in body)
            self.assertTrue('Meta</summary>' in body)
            self.assertTrue('name="status"' in body)
            self.assertTrue('form-control-plaintext' not in body)
            self.assertTrue('name="created' not in body)

    def test_form_sections(self):
        self.create_users()
        entry = self.create_entry()
        entry_admin = admin._registry[Entry]

        def summarize(sections):
            return [(label, collapsed,
                     [f.name if f is not None else lbl for f, lbl, v in rows])
                    for label, collapsed, rows in sections]

        form = entry_admin.get_edit_form(entry)(obj=entry)
        sections = entry_admin.get_form_sections(form, entry)
        self.assertEqual(summarize(sections), [
            ('Content', False, ['title', 'body']),
            ('Meta', True, ['Created']),
            (None, False, ['status']),
        ])

        # the readonly row resolves the instance value.
        self.assertEqual(sections[1][2][0][2], entry.created)

        # adding: same sections, readonly row dropped.
        form = entry_admin.get_add_form()()
        self.assertEqual(summarize(entry_admin.get_form_sections(form)), [
            ('Content', False, ['title', 'body']),
            ('Meta', True, []),
            (None, False, ['status']),
        ])

    def test_readonly_with_whitelist(self):
        class SubsetAdmin(ModelAdmin):
            fields = ('title', 'created')
            readonly_fields = ('created',)

        form = SubsetAdmin(admin, Entry).get_form()()
        self.assertEqual(list(form._fields), ['title'])

        # a whitelist that is entirely readonly yields an empty form rather
        # than falling through to every field.
        class LockedAdmin(ModelAdmin):
            fields = ('created',)
            readonly_fields = ('created',)

        form = LockedAdmin(admin, Entry).get_form()()
        self.assertEqual(list(form._fields), [])

    def test_falsy_form_field(self):
        self.create_users()
        entry = self.create_entry()
        entry_admin = admin._registry[Entry]

        # an empty bound FieldList is falsy. the row dispatch must test
        # field None, not truthiness, or this renders as a readonly row.
        class ListForm(entry_admin.get_form()):
            extras = FieldList(StringField('Extra'))

        entry_admin.get_form = lambda adding=False: ListForm
        try:
            with self.flask_app.test_client() as c:
                self.login(c)
                body = c.get('/admin/entry/%d/' % entry.id).data.decode('utf-8')
                self.assertTrue('id="extras"' in body)
                self.assertEqual(body.count('form-control-plaintext'), 1)
        finally:
            del entry_admin.get_form


class AdminPermissionsTestCase(BaseAdminTestCase):
    # Comment is registered read-only (all three flags off), Ping with
    # can_delete off and a user-aware check_edit.

    def assertForbidden(self, c, url, data, post_url=None):
        self.assertEqual(c.get(url).status_code, 403)
        self.assertEqual(c.post(post_url or url, data=data).status_code, 403)

    def test_read_only_model(self):
        self.create_users()
        comment = Comment.create(user=self.normal, body='c1')

        with self.flask_app.test_client() as c:
            self.login(c)

            # reads stay reachable.
            self.assertEqual(c.get('/admin/comment/').status_code, 200)
            self.assertEqual(c.get('/admin/comment/export/').status_code, 200)
            self.assertEqual(c.get('/admin/comment/_ajax/').status_code, 200)

            self.assertForbidden(c, '/admin/comment/add/',
                                 {'user': self.normal.id, 'body': 'new'})
            self.assertForbidden(c, '/admin/comment/%d/' % comment.id,
                                 {'user': self.normal.id, 'body': 'edited'})
            self.assertForbidden(
                c, '/admin/comment/delete/?id=%d' % comment.id,
                {'id': comment.id}, post_url='/admin/comment/delete/')

            # the index delete action 403s, export still redirects.
            resp = c.post('/admin/comment/',
                          data={'action': 'delete', 'id': comment.id})
            self.assertEqual(resp.status_code, 403)
            resp = c.post('/admin/comment/',
                          data={'action': 'export', 'id': comment.id})
            self.assertRedirect(resp)

        # nothing was created, changed or deleted.
        self.assertEqual(Comment.select().count(), 1)
        self.assertEqual(Comment.get(id=comment.id).body, 'c1')

    def test_read_only_index_html(self):
        self.create_users()
        comment = Comment.create(user=self.normal, body='c1')
        note = Note.create(user=self.normal, message='n1')

        with self.flask_app.test_client() as c:
            self.login(c)

            # denied links disappear from the read-only index.
            body = c.get('/admin/comment/').data.decode('utf-8')
            self.assertNotIn('Add new', body)
            self.assertNotIn('/admin/comment/add/', body)
            self.assertNotIn('/admin/comment/%d/' % comment.id, body)
            self.assertNotIn('/admin/comment/delete/', body)
            self.assertNotIn("index_submit('delete')", body)

            # a default admin still renders all of them.
            body = c.get('/admin/note/').data.decode('utf-8')
            self.assertIn('Add new', body)
            self.assertIn('/admin/note/add/', body)
            self.assertIn('/admin/note/%d/' % note.id, body)
            self.assertIn('/admin/note/delete/', body)
            self.assertIn("index_submit('delete')", body)

    def test_dashboard_add_link(self):
        self.create_users()

        with self.flask_app.test_client() as c:
            self.login(c)
            body = c.get('/admin/').data.decode('utf-8')
            self.assertIn('/admin/note/add/', body)
            self.assertNotIn('/admin/comment/add/', body)

    def test_edit_page_delete_button(self):
        self.create_users()
        ping = Ping.create(user=self.normal, body='p1')
        note = Note.create(user=self.normal, message='n1')

        with self.flask_app.test_client() as c:
            self.login(c)

            body = c.get('/admin/note/%d/' % note.id).data.decode('utf-8')
            self.assertIn('/admin/note/delete/', body)

            body = c.get('/admin/ping/%d/' % ping.id).data.decode('utf-8')
            self.assertNotIn('/admin/ping/delete/', body)

    def test_user_aware_check_edit(self):
        self.create_users()
        self.create_user('admin2', 'admin2', admin=True)
        ping = Ping.create(user=self.normal, body='p1')

        with self.flask_app.test_client() as c:
            self.login(c)

            # "admin" may edit, and index rows link to the edit page.
            self.assertEqual(
                c.get('/admin/ping/%d/' % ping.id).status_code, 200)
            body = c.get('/admin/ping/').data.decode('utf-8')
            self.assertIn('/admin/ping/%d/' % ping.id, body)

        with self.flask_app.test_client() as c:
            c.post('/accounts/login/',
                   data={'username': 'admin2', 'password': 'admin2'})

            # "admin2" cannot edit but may still browse and add.
            self.assertForbidden(c, '/admin/ping/%d/' % ping.id,
                                 {'user': self.normal.id, 'body': 'x'})
            self.assertEqual(Ping.get(id=ping.id).body, 'p1')

            self.assertEqual(c.get('/admin/ping/').status_code, 200)
            self.assertEqual(c.get('/admin/ping/add/').status_code, 200)

            body = c.get('/admin/ping/').data.decode('utf-8')
            self.assertNotIn('/admin/ping/%d/' % ping.id, body)


class ShippedPanelTestCase(BaseAdminTestCase):
    def setUp(self):
        super(ShippedPanelTestCase, self).setUp()
        self.create_users()
        self.login()

    def get_dashboard(self):
        resp = self.app.get('/admin/')
        self.assertEqual(resp.status_code, 200)
        return resp.data.decode('utf-8')

    def render_panel(self, panel):
        with self.flask_app.test_request_context('/'):
            auth.login_user(self.admin)
            return panel.render()

    def test_recent_rows_panel(self):
        for i in range(7):
            self.create_message(self.admin, 'message-%s' % i,
                                pub_date=datetime.datetime(2026, 1, i + 1))
        body = self.get_dashboard()

        for i in range(2, 7):
            self.assertIn('message-%s' % i, body)
        self.assertNotIn('message-0', body)
        self.assertNotIn('message-1', body)

        newest = Message.select().order_by(Message.pub_date.desc()).get()
        edit_url = '/admin/message/%s/' % newest.id
        self.assertIn('href="%s"' % edit_url, body)
        self.assertEqual(self.app.get(edit_url).status_code, 200)

    def test_recent_rows_default_ordering(self):
        for i in range(7):
            Note.create(user=self.admin, message='note-%s' % i)

        panel = RecentRowsPanel(admin, 'Latest notes', Note)
        notes = list(panel.get_context()['object_list'])
        self.assertEqual([note.message for note in notes],
                         ['note-6', 'note-5', 'note-4', 'note-3', 'note-2'])

    def test_recent_rows_columns(self):
        panel = admin._panels['Recent messages']
        self.assertEqual(panel.get_context()['columns'],
                         admin._registry[Message].columns)

        panel = RecentRowsPanel(admin, 'Recent tweets', Tweet)
        self.assertIsNone(panel.get_context()['columns'])

    def test_recent_rows_empty(self):
        self.assertIn('No records.', self.get_dashboard())

    def test_recent_rows_readonly_admin(self):
        Comment.create(user=self.admin, body='comment-body')
        panel = RecentRowsPanel(admin, 'Recent comments', Comment)
        html = self.render_panel(panel)
        self.assertIn('comment-body', html)
        self.assertNotIn('<a href', html)

    def test_recent_rows_unregistered_model(self):
        Tweet.create(user=self.admin, content='tweet-body')
        panel = RecentRowsPanel(admin, 'Recent tweets', Tweet,
                                columns=('content',))
        html = self.render_panel(panel)
        self.assertIn('tweet-body', html)
        self.assertNotIn('None', html)
        self.assertNotIn('<a href', html)


class LinkAdmin(ModelAdmin):
    filter_fields = ('src', 'dst', 'src__username', 'dst__username')
    search_fields = ('label', 'dst__username')


class AdminFilterTestCase(BaseAdminTestCase):
    def setUp(self):
        super(AdminFilterTestCase, self).setUp()
        models = [AModel, BModel, CModel, DModel, BDetails, TSModel]
        db.database.drop_tables(models)
        db.database.create_tables(models)

    def create_models(self):
        for i in range(1, 4):
            a = AModel.create(a_field='a%d' % i)
            b = BModel.create(b_field='b%d' % i, a=a)
            c = CModel.create(c_field='c%d' % i, b=b)
            d = DModel.create(d_field='d%d' % i, c=c)
            if i % 2 == 0:
                bd = BDetails.create(b=b)

    def test_filters(self):
        users = self.create_users()
        self.create_models()

        with self.flask_app.test_client() as c:
            self.login(c)

            resp = c.get('/admin/dmodel/?fr_c-fr_b-fr_a-fo_a_field=0&fr_c-fr_b-fr_a-fv_a_field=a1')
            query = self.get_context('query')

            self.assertEqual([o.d_field for o in query.get_list()], ['d1'])

            resp = c.get('/admin/dmodel/?fr_c-fr_b-fr_a-fo_a_field=0&fr_c-fr_b-fr_a-fv_a_field=a3')
            query = self.get_context('query')

            self.assertEqual([o.d_field for o in query.get_list()], ['d3'])

            resp = c.get('/admin/dmodel/?fr_c-fr_b-fo_a=0&fr_c-fr_b-fv_a=2')
            query = self.get_context('query')

            self.assertEqual([o.d_field for o in query.get_list()], ['d2'])

    def test_filter_ne_multiple_values(self):
        # two "not equal" values for one field exclude both, rather than the
        # old OR that left every row matching.
        self.create_users()
        for i in range(1, 4):
            AModel.create(a_field='a%d' % i)

        with self.flask_app.test_client() as c:
            self.login(c)
            c.get('/admin/amodel/?fo_a_field=ne&fv_a_field=a1'
                  '&fo_a_field=ne&fv_a_field=a2')
            query = self.get_context('query')
            self.assertEqual([o.a_field for o in query.get_list()], ['a3'])

    def test_related_tree_diamond(self):
        # two foreign keys to one model must each expand that model's subtree,
        # for filters and for export. a shared `seen` set let only the first
        # path through, so the second lost the nested fields.
        import peewee
        mem = peewee.SqliteDatabase(':memory:')

        class M(peewee.Model):
            class Meta:
                database = mem

        class Grp(M):
            name = peewee.CharField()

        class Usr(M):
            username = peewee.CharField()
            grp = peewee.ForeignKeyField(Grp)

        class Lnk(M):
            src = peewee.ForeignKeyField(Usr, backref='s')
            dst = peewee.ForeignKeyField(Usr, backref='d')
            label = peewee.CharField()

        # filter tree: both fk paths reach grp.
        tree = make_field_tree(Lnk, None, [])
        self.assertEqual(list(tree.children['src'].children), ['grp'])
        self.assertEqual(list(tree.children['dst'].children), ['grp'])

        # export: both nested paths collect Grp's columns.
        accum = ModelAdmin(admin, Lnk).collect_related_fields(Lnk, {}, [])
        paths = {path for (_model, path) in accum}
        self.assertIn('src__grp', paths)
        self.assertIn('dst__grp', paths)

    def test_related_tree_depth_cap(self):
        # the walk stops after max_filter_depth (3) hops, so a long fk chain
        # cannot explode the tree.
        import peewee
        mem = peewee.SqliteDatabase(':memory:')

        class M(peewee.Model):
            class Meta:
                database = mem

        class C4(M):
            v = peewee.CharField()

        class C3(M):
            nxt = peewee.ForeignKeyField(C4)

        class C2(M):
            nxt = peewee.ForeignKeyField(C3)

        class C1(M):
            nxt = peewee.ForeignKeyField(C2)

        class C0(M):
            nxt = peewee.ForeignKeyField(C1)

        tree = make_field_tree(C0, None, [])
        hop3 = tree.children['nxt'].children['nxt'].children['nxt']  # C3
        # C3's own fk is still filterable by id, but C4 is beyond the cap.
        self.assertIn('nxt', [f.name for f in hop3.fields])
        self.assertEqual(list(hop3.children), [])

    def assertFieldTree(self, expected):
        field_tree = self.get_context('field_tree')

        # convert to dict
        field_dict = {}
        queue = [field_tree]
        while queue:
            node = queue.pop(0)
            field_dict[node.model] = [f.name for f in node.fields]
            queue.extend(node.children.values())

        self.assertEqual(field_dict, expected)

    def test_lookups(self):
        users = self.create_users()

        with self.flask_app.test_client() as c:
            self.login(c)

            resp = c.get('/admin/amodel/')
            self.assertFieldTree({
                AModel: ['id', 'a_field'],
            })

            resp = c.get('/admin/bmodel/')
            self.assertFieldTree({
                AModel: ['id', 'a_field'],
                BModel: ['id', 'a', 'b_field'],
            })

            resp = c.get('/admin/cmodel/')
            self.assertFieldTree({
                AModel: ['id', 'a_field'],
                BModel: ['id', 'a', 'b_field'],
                CModel: ['id', 'b', 'c_field'],
            })

            resp = c.get('/admin/dmodel/')
            self.assertFieldTree({
                AModel: ['id', 'a_field'],
                BModel: ['id', 'a', 'b_field'],
                CModel: ['id', 'b', 'c_field'],
                DModel: ['id', 'c', 'd_field'],
            })

    def test_timestamp_filters(self):
        # Regression: a TimestampField is stored as an integer but represents a
        # datetime.  It used to fall through to plain numeric filtering, and its
        # value could not be cleaned (TimestampField.db_value chokes on the
        # picker string), so process_request silently dropped the filter and the
        # query came back unfiltered.  It should behave like a DateTimeField.
        now = datetime.datetime.now()
        TSModel.create(ts=datetime.datetime(2024, 1, 15, 12), label='y2024')
        TSModel.create(ts=datetime.datetime(2020, 6, 1), label='y2020')
        TSModel.create(ts=now, label='today')

        ts_field = TSModel._meta.fields['ts']

        # the field offers the date-aware operators, not just numeric ones
        ff = FilterForm(TSModel, FilterModelConverter(), FilterMapping())
        ops = set(qf.key for qf in ff._query_filters[ts_field])
        self.assertTrue({'within_days', 'older_days', 'year', 'month'} <= ops)

        def run(op, value):
            qs = '/?fo_ts=%s&fv_ts=%s' % (op, value)
            with self.flask_app.test_request_context(qs):
                form = FilterForm(TSModel, FilterModelConverter(), FilterMapping())
                _, query, cleaned = form.process_request(TSModel.select())
                return set(o.label for o in query), bool(cleaned)

        # comparisons now apply (the bug: they were silently dropped, so the
        # query returned all three rows with cleaned == []).
        self.assertEqual(run('gt', '2022-01-01T00:00:00'), ({'y2024', 'today'}, True))
        self.assertEqual(run('lt', '2022-01-01T00:00:00'), ({'y2020'}, True))
        self.assertEqual(run('eq', '2024-01-15T12:00:00'), ({'y2024'}, True))
        # date-aware operators work against the integer column
        self.assertEqual(run('year', '2020'), ({'y2020'}, True))
        self.assertEqual(run('within_days', '2'), ({'today'}, True))

    def test_filter_two_fks_same_model(self):
        # two foreign keys to one model must join through separate aliases, so a
        # filter on both does not collapse to one join with contradictory
        # predicates (which returned nothing).
        self.create_users()
        a, b = self.admin, self.normal
        Link.create(src=a, dst=b, label='a-to-b')
        Link.create(src=b, dst=a, label='b-to-a')

        link_admin = LinkAdmin(admin, Link)
        qs = ('/?fr_src-fo_username=eq&fr_src-fv_username=%s'
              '&fr_dst-fo_username=eq&fr_dst-fv_username=%s' % (a.username, b.username))
        with self.flask_app.test_request_context(qs):
            _, query, _, _ = link_admin.process_filters(Link.select())
            labels = [l.label for l in query]
        self.assertEqual(labels, ['a-to-b'])

    def test_search_left_joins_nullable_fk(self):
        # search LEFT OUTER joins the fk path, so a row whose nullable fk is null
        # still appears when it matches a direct search field.
        self.create_users()
        a = self.admin
        Link.create(src=a, dst=a, label='has-dst')
        Link.create(src=a, dst=None, label='null-dst-findme')

        link_admin = LinkAdmin(admin, Link)
        query = link_admin.apply_search(Link.select(), 'findme')
        self.assertEqual([l.label for l in query], ['null-dst-findme'])

    def test_export_two_fks_same_model(self):
        # two foreign keys to one model export through separate aliased joins
        # instead of raising "more than one foreign key".
        self.create_users()
        Link.create(src=self.admin, dst=self.normal, label='ab')

        related = LinkAdmin(admin, Link).collect_related_fields(Link, {}, [])
        export = Export(Link.select(), related, ['src__username', 'dst__username'])
        prepared, field_dict = export.prepare_query()
        rows = [Serializer().serialize_object(o, field_dict) for o in prepared]
        self.assertEqual(rows, [
            {'src': {'username': 'admin'}, 'dst': {'username': 'normal'}}])

    def test_export_related_field_without_fk_column(self):
        # a related column serializes even when its fk column was not also
        # selected (the fk name is added so the serializer recurses).
        self.create_users()
        Message.create(user=self.admin, content='hi')

        related = admin._registry[Message].collect_related_fields(Message, {}, [])
        export = Export(Message.select(), related, ['content', 'user__username'])
        prepared, field_dict = export.prepare_query()
        rows = [Serializer().serialize_object(o, field_dict) for o in prepared]
        self.assertEqual(rows, [{'content': 'hi', 'user': {'username': 'admin'}}])

    def test_export_fk_to_non_pk_field(self):
        # an fk that references a non-pk field must select that field on the
        # alias, not the related model's primary key.
        class Coded(db.Model):
            code = CharField(unique=True)
            label = CharField()
        class CodedRef(db.Model):
            coded = ForeignKeyField(Coded, field='code')
            note = CharField()

        db.database.create_tables([Coded, CodedRef])
        try:
            CodedRef.create(coded=Coded.create(code='abc', label='Alpha'), note='n1')
            related = ModelAdmin(admin, CodedRef).collect_related_fields(CodedRef, {}, [])
            export = Export(CodedRef.select(), related, ['note', 'coded__label'])
            prepared, field_dict = export.prepare_query()
            rows = [Serializer().serialize_object(o, field_dict) for o in prepared]
            self.assertEqual(rows, [{'note': 'n1', 'coded': {'label': 'Alpha'}}])
        finally:
            db.database.drop_tables([CodedRef, Coded])


class TemplateHelperTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(TemplateHelperTestCase, self).setUp()
        self.create_users()
        self.create_message(self.admin, 'admin message')
        self.create_message(self.admin, 'admin message 2')
        self.create_message(self.normal, 'normal message')

    def test_get_model_field(self):
        self.assertEqual(admin.get_model_field(self.admin, 'username'), 'admin')
        self.assertEqual(admin.get_model_field(self.admin, 'message_count'), 2)
        self.assertRaises(AttributeError, admin.get_model_field, self.admin, 'missing_attr')

    def test_get_form_field(self):
        form = model_form(User)(obj=self.admin)
        self.assertEqual(admin.get_form_field(form, 'username'), form.username)
        self.assertEqual(admin.get_form_field(form, 'username').data, 'admin')

    def test_fix_underscores(self):
        self.assertEqual(admin.fix_underscores('some_model'), 'Some Model')
        self.assertEqual(admin.fix_underscores('test'), 'Test')

    def test_update_querystring(self):
        qs = lambda t: str(t).encode('utf8')
        self.assertEqual(admin.update_querystring(qs(''), 'page', 1), 'page=1')
        self.assertEqual(admin.update_querystring(qs('page=1'), 'page', 2), 'page=2')
        self.assertEqual(admin.update_querystring(qs('session=3&page=1'), 'page', 2), 'session=3&page=2')
        self.assertEqual(admin.update_querystring(qs('page=1&session=3'), 'page', 2), 'session=3&page=2')
        self.assertEqual(admin.update_querystring(qs('session=3&page=1&ordering=id'), 'page', 2), 'session=3&ordering=id&page=2')
        self.assertEqual(admin.update_querystring(qs('session=3&ordering=id'), 'page', 2), 'session=3&ordering=id&page=2')
        # a value that contains the key name as a substring is not corrupted.
        self.assertEqual(admin.update_querystring(qs('q=rampage&page=1'), 'page', 2),
                         'q=rampage&page=2')
        # clearing 'q' preserves filter params whose values embed the key.
        self.assertEqual(admin.update_querystring(qs('q=hello&fo_content=eq'), 'q', ''),
                         'fo_content=eq&q=')

    def test_get_verbose_name(self):
        self.assertEqual(admin.get_verbose_name(User, 'username'), 'Username')
        self.assertEqual(admin.get_verbose_name(User, 'join_date'), 'Join Date')
        self.assertEqual(admin.get_verbose_name(User, 'admin'), 'Can access admin')
        self.assertEqual(admin.get_verbose_name(User, 'some_field'), 'Some Field')

    def test_get_model_admins(self):
        self.assertEqual(admin.get_model_admins(), [
            admin._registry[AModel],
            admin._registry[BDetails],
            admin._registry[BModel],
            admin._registry[CModel],
            admin._registry[Comment],
            admin._registry[DModel],
            admin._registry[Entry],
            admin._registry[Message],
            admin._registry[Note],
            admin._registry[Ping],
            admin._registry[ScopedItem],
            admin._registry[ScopedRef],
            admin._registry[User],
        ])
