import base64
import datetime
import hashlib
import json
import unittest

from flask import g

from flask_peewee.rest import Authentication
from flask_peewee.rest import RestAPI
from flask_peewee.rest import RestResource
from flask_peewee.rest import UserAuthentication
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import AModel
from flask_peewee.tests.test_app import APIKey
from flask_peewee.tests.test_app import ApiToken
from flask_peewee.tests.test_app import BDetails
from flask_peewee.tests.test_app import BModel
from flask_peewee.tests.test_app import BearerDoc
from flask_peewee.tests.test_app import BulkItem
from flask_peewee.tests.test_app import CModel
from flask_peewee.tests.test_app import Comment
from flask_peewee.tests.test_app import DModel
from flask_peewee.tests.test_app import EModel
from flask_peewee.tests.test_app import FModel
from flask_peewee.tests.test_app import GModel
from flask_peewee.tests.test_app import HModel
from flask_peewee.tests.test_app import HashedDoc
from flask_peewee.tests.test_app import HashedToken
from flask_peewee.tests.test_app import Link
from flask_peewee.tests.test_app import Message
from flask_peewee.tests.test_app import Note
from flask_peewee.tests.test_app import Ping
from flask_peewee.tests.test_app import TestModel
from flask_peewee.tests.test_app import Tweet
from flask_peewee.tests.test_app import User
from flask_peewee.tests.test_app import api
from flask_peewee.tests.test_app import db
from flask_peewee.utils import check_password
from flask_peewee.utils import get_next
from flask_peewee.utils import make_password


class RestApiTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(RestApiTestCase, self).setUp()
        models = [TestModel, APIKey, BearerDoc, BulkItem]
        db.database.drop_tables(models)
        db.database.create_tables(models)

    def response_json(self, response):
        return json.loads(response.data.decode('utf8'))

    def post_to(self, url, data):
        return self.app.post(url, data=json.dumps(data))

    def auth_headers(self, username, password):
        data = '%s:%s' % (username, password)
        return {'Authorization': 'Basic %s' % base64.b64encode(data.encode('utf8')).decode('utf8')}

    def bearer(self, token):
        return {'Authorization': 'Bearer %s' % token}

    def conv_date(self, dt):
        return dt.isoformat()

    def assertAPIResponse(self, resp_json, body):
        self.assertEqual(body, resp_json['objects'])

    def assertAPIMeta(self, resp_json, meta):
        actual = dict(resp_json['meta'])
        # object_count is asserted explicitly where relevant; ignore it here
        # unless the expectation opts in.
        if 'object_count' not in meta:
            actual.pop('object_count', None)
        self.assertEqual(meta, actual)

    def assertAPIUser(self, json_data, user):
        self.assertEqual(json_data, {
            'username': user.username,
            'active': user.active,
            'join_date': self.conv_date(user.join_date),
            'admin': user.admin,
            'id': user.id,
        })

    def assertAPIUsers(self, json_data, users):
        for json_item, user in zip(json_data['objects'], users):
            self.assertAPIUser(json_item, user)

    def assertAPINote(self, json_data, note):
        self.assertEqual(json_data, {
            'user': note.user.id,
            'message': note.message,
            'created_date': self.conv_date(note.created_date),
            'id': note.id,
        })

    def assertAPINotes(self, json_data, notes):
        for json_item, note in zip(json_data['objects'], notes):
            self.assertAPINote(json_item, note)

    def assertAPIMessage(self, json_data, message):
        self.assertEqual(json_data, {
            'user': message.user.id,
            'content': message.content,
            'pub_date': self.conv_date(message.pub_date),
            'id': message.id,
        })

    def assertAPIMessages(self, json_data, messages):
        for json_item, message in zip(json_data['objects'], messages):
            self.assertAPIMessage(json_item, message)

    def assertAPITestModel(self, json_data, tm):
        self.assertEqual(json_data, {
            'data': tm.data,
            'id': tm.id,
        })

    def assertAPITestModels(self, json_data, tms):
        for json_item, tm in zip(json_data['objects'], tms):
            self.assertAPITestModel(json_item, tm)


class RestApiResourceTestCase(RestApiTestCase):
    def setUp(self):
        super(RestApiResourceTestCase, self).setUp()
        for M in (FModel, EModel, DModel, CModel, BDetails, BModel, AModel):
            M.delete().execute()

    def create_test_models(self):
        self.a1 = AModel.create(a_field='a1')
        self.a2 = AModel.create(a_field='a2')
        self.b1 = BModel.create(b_field='b1', a=self.a1)
        self.b2 = BModel.create(b_field='b2', a=self.a2)
        self.c1 = CModel.create(c_field='c1', b=self.b1)
        self.c2 = CModel.create(c_field='c2', b=self.b2)

        self.e1 = EModel.create(e_field='e1')
        self.e2 = EModel.create(e_field='e2')
        self.f1 = FModel.create(f_field='f1', e=self.e1)
        self.f2 = FModel.create(f_field='f2')

    def test_resources_list_detail(self):
        self.create_test_models()

        # amodel
        resp = self.app.get('/api/amodel/?ordering=id')
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json['objects'], [
            {'id': self.a1.id, 'a_field': 'a1'},
            {'id': self.a2.id, 'a_field': 'a2'},
        ])

        resp = self.app.get('/api/amodel/%s/' % self.a2.id)
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json, {
            'id': self.a2.id,
            'a_field': 'a2',
        })

        # bmodel
        resp = self.app.get('/api/bmodel/?ordering=id')
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json['objects'], [
            {'id': self.b1.id, 'b_field': 'b1', 'a': {'id': self.a1.id, 'a_field': 'a1'}},
            {'id': self.b2.id, 'b_field': 'b2', 'a': {'id': self.a2.id, 'a_field': 'a2'}},
        ])

        resp = self.app.get('/api/bmodel/%s/' % self.b2.id)
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json, {
            'id': self.b2.id,
            'b_field': 'b2',
            'a': {'id': self.a2.id, 'a_field': 'a2'},
        })

        # cmodel
        resp = self.app.get('/api/cmodel/?ordering=id')
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json['objects'], [
            {'id': self.c1.id, 'c_field': 'c1', 'b': {'id': self.b1.id, 'b_field': 'b1', 'a': {'id': self.a1.id, 'a_field': 'a1'}}},
            {'id': self.c2.id, 'c_field': 'c2', 'b': {'id': self.b2.id, 'b_field': 'b2', 'a': {'id': self.a2.id, 'a_field': 'a2'}}},
        ])

        resp = self.app.get('/api/cmodel/%s/' % self.c2.id)
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json, {
            'id': self.c2.id,
            'c_field': 'c2',
            'b': {'id': self.b2.id, 'b_field': 'b2', 'a': {'id': self.a2.id, 'a_field': 'a2'}},
        })

        # fmodel
        resp = self.app.get('/api/fmodel/?ordering=id')
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json['objects'], [
            {'id': self.f1.id, 'f_field': 'f1', 'e': {'id': self.e1.id, 'e_field': 'e1'}},
            {'id': self.f2.id, 'f_field': 'f2', 'e': None},
        ])

        resp = self.app.get('/api/fmodel/%s/' % self.f1.id)
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json, {
            'id': self.f1.id,
            'f_field': 'f1',
            'e': {'id': self.e1.id, 'e_field': 'e1'},
        })

        resp = self.app.get('/api/fmodel/%s/' % self.f2.id)
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json, {
            'id': self.f2.id,
            'f_field': 'f2',
            'e': None,
        })

    def test_resources_create(self):
        # a model
        resp = self.post_to('/api/amodel/', {'a_field': 'ax'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(AModel.select().count(), 1)
        a_obj = AModel.get(a_field='ax')
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': a_obj.id,
            'a_field': 'ax',
        })

        # b model
        resp = self.post_to('/api/bmodel/', {'b_field': 'by', 'a': {'a_field': 'ay'}})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(BModel.select().count(), 1)
        self.assertEqual(AModel.select().count(), 2)
        b_obj = BModel.get(b_field='by')
        a_obj = AModel.get(a_field='ay')

        self.assertEqual(b_obj.a, a_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': b_obj.id,
            'b_field': 'by',
            'a': {
                'id': a_obj.id,
                'a_field': 'ay',
            },
        })

        # c model
        resp = self.post_to('/api/cmodel/', {'c_field': 'cz', 'b': {'b_field': 'bz', 'a': {'a_field': 'az'}}})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(CModel.select().count(), 1)
        self.assertEqual(BModel.select().count(), 2)
        self.assertEqual(AModel.select().count(), 3)
        c_obj = CModel.get(c_field='cz')
        b_obj = BModel.get(b_field='bz')
        a_obj = AModel.get(a_field='az')

        self.assertEqual(c_obj.b, b_obj)
        self.assertEqual(b_obj.a, a_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': c_obj.id,
            'c_field': 'cz',
            'b': {
                'id': b_obj.id,
                'b_field': 'bz',
                'a': {
                    'id': a_obj.id,
                    'a_field': 'az',
                },
            },
        })

        # f model
        resp = self.post_to('/api/fmodel/', {'f_field': 'fy', 'e': {'e_field': 'ey'}})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(FModel.select().count(), 1)
        self.assertEqual(EModel.select().count(), 1)
        f_obj = FModel.get(f_field='fy')
        e_obj = EModel.get(e_field='ey')

        self.assertEqual(f_obj.e, e_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': f_obj.id,
            'f_field': 'fy',
            'e': {
                'id': e_obj.id,
                'e_field': 'ey',
            },
        })

        resp = self.post_to('/api/fmodel/', {'f_field': 'fz'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(FModel.select().count(), 2)
        self.assertEqual(EModel.select().count(), 1)
        f_obj = FModel.get(f_field='fz')

        self.assertEqual(f_obj.e, None)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': f_obj.id,
            'f_field': 'fz',
            'e': None,
        })

    def test_create_invalid_returns_400(self):
        # malformed JSON body -> 400 with a JSON error, not a 500.
        resp = self.app.post('/api/amodel/', data='{not json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.mimetype, 'application/json')
        self.assertIn('error', json.loads(resp.data.decode('utf8')))
        self.assertEqual(AModel.select().count(), 0)

        # missing required column (b_field / a) -> IntegrityError surfaced as 400.
        resp = self.post_to('/api/bmodel/', {'b_field': 'orphan'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.mimetype, 'application/json')
        self.assertIn('error', json.loads(resp.data.decode('utf8')))
        self.assertEqual(BModel.select().count(), 0)

    def test_resources_edit(self):
        self.create_test_models()

        # a
        resp = self.post_to('/api/amodel/%s/' % self.a2.id, {'a_field': 'a2-xxx'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(AModel.select().count(), 2)
        a_obj = AModel.get(id=self.a2.id)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': self.a2.id,
            'a_field': 'a2-xxx',
        })

        # b
        resp = self.post_to('/api/bmodel/%s/' % self.b2.id, {'b_field': 'b2-yyy', 'a': {'a_field': 'a2-yyy'}})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(BModel.select().count(), 2)
        self.assertEqual(AModel.select().count(), 2)
        b_obj = BModel.get(id=self.b2.id)
        a_obj = AModel.get(id=self.a2.id)

        self.assertEqual(b_obj.a, a_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': b_obj.id,
            'b_field': 'b2-yyy',
            'a': {
                'id': a_obj.id,
                'a_field': 'a2-yyy',
            },
        })

        # c
        resp = self.post_to('/api/cmodel/%s/' % self.c2.id, {'c_field': 'c2-zzz', 'b': {'b_field': 'b2-zzz', 'a': {'a_field': 'a2-zzz'}}})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(CModel.select().count(), 2)
        self.assertEqual(BModel.select().count(), 2)
        self.assertEqual(AModel.select().count(), 2)
        c_obj = CModel.get(id=self.c2.id)
        b_obj = BModel.get(id=self.b2.id)
        a_obj = AModel.get(id=self.a2.id)

        self.assertEqual(c_obj.b, b_obj)
        self.assertEqual(b_obj.a, a_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': c_obj.id,
            'c_field': 'c2-zzz',
            'b': {
                'id': b_obj.id,
                'b_field': 'b2-zzz',
                'a': {
                    'id': a_obj.id,
                    'a_field': 'a2-zzz',
                },
            },
        })

        # f
        resp = self.post_to('/api/fmodel/%s/' % self.f1.id, {'f_field': 'f1-yyy', 'e': {'e_field': 'e1-yyy'}})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(FModel.select().count(), 2)
        self.assertEqual(EModel.select().count(), 2)
        f_obj = FModel.get(id=self.f1.id)
        e_obj = EModel.get(id=self.e1.id)

        self.assertEqual(f_obj.e, e_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': f_obj.id,
            'f_field': 'f1-yyy',
            'e': {
                'id': e_obj.id,
                'e_field': 'e1-yyy',
            },
        })

        resp = self.post_to('/api/fmodel/%s/' % self.f2.id, {'f_field': 'f2-yyy'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(FModel.select().count(), 2)
        self.assertEqual(EModel.select().count(), 2)
        f_obj = FModel.get(id=self.f2.id)

        self.assertEqual(f_obj.e, None)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': f_obj.id,
            'f_field': 'f2-yyy',
            'e': None,
        })


    def test_resource_edit_partial(self):
        self.create_test_models()

        # b model
        resp = self.post_to('/api/bmodel/%s/' % self.b2.id, {'b_field': 'b2-yyy'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(BModel.select().count(), 2)
        self.assertEqual(AModel.select().count(), 2)
        b_obj = BModel.get(id=self.b2.id)
        a_obj = AModel.get(id=self.a2.id)

        self.assertEqual(b_obj.a, a_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': b_obj.id,
            'b_field': 'b2-yyy',
            'a': {
                'id': a_obj.id,
                'a_field': 'a2',
            },
        })

        # f model
        resp = self.post_to('/api/fmodel/%s/' % self.f1.id, {'f_field': 'f1-zzz'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(FModel.select().count(), 2)
        self.assertEqual(EModel.select().count(), 2)
        f_obj = FModel.get(id=self.f1.id)
        e_obj = EModel.get(id=self.e1.id)

        self.assertEqual(f_obj.e, e_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': f_obj.id,
            'f_field': 'f1-zzz',
            'e': {
                'id': e_obj.id,
                'e_field': 'e1',
            },
        })

    def test_resource_patch_partial(self):
        # PATCH edits like PUT, changing only the fields present in the body.
        self.create_test_models()

        resp = self.app.patch('/api/bmodel/%s/' % self.b2.id,
                              data=json.dumps({'b_field': 'b2-patched'}))
        self.assertEqual(resp.status_code, 200)

        b_obj = BModel.get(id=self.b2.id)
        self.assertEqual(b_obj.a, self.a2)
        self.assertEqual(self.response_json(resp), {
            'id': b_obj.id,
            'b_field': 'b2-patched',
            'a': {
                'id': self.a2.id,
                'a_field': 'a2',
            },
        })

    def test_resource_edit_by_fk(self):
        self.create_test_models()

        # b model
        resp = self.post_to('/api/bmodel/%s/' % self.b2.id, {'a': self.a1.id})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(BModel.select().count(), 2)
        self.assertEqual(AModel.select().count(), 2)
        b_obj = BModel.get(id=self.b2.id)
        a_obj = AModel.get(id=self.a1.id)

        self.assertEqual(b_obj.a, a_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': b_obj.id,
            'b_field': 'b2',
            'a': {
                'id': a_obj.id,
                'a_field': 'a1',
            },
        })

        # f model
        resp = self.post_to('/api/fmodel/%s/' % self.f2.id, {'e': self.e2.id})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(BModel.select().count(), 2)
        self.assertEqual(AModel.select().count(), 2)
        f_obj = FModel.get(id=self.f2.id)
        e_obj = EModel.get(id=self.e2.id)

        self.assertEqual(f_obj.e, e_obj)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': f_obj.id,
            'f_field': 'f2',
            'e': {
                'id': e_obj.id,
                'e_field': 'e2',
            },
        })

    def test_delete(self):
        self.create_test_models()

        resp = self.post_to('/api/cmodel/%s/delete/' % self.c2.id, {})
        self.assertEqual(json.loads(resp.data.decode('utf8')), {'deleted': 1})

        self.assertEqual(CModel.select().count(), 1)
        self.assertEqual(BModel.select().count(), 2)
        self.assertEqual(AModel.select().count(), 2)

        resp = self.post_to('/api/amodel/%s/delete/' % self.a1.id, {})
        self.assertEqual(json.loads(resp.data.decode('utf8')), {'deleted': 1})

        self.assertEqual(CModel.select().count(), 0)
        self.assertEqual(BModel.select().count(), 1)
        self.assertEqual(AModel.select().count(), 1)

        resp = self.post_to('/api/emodel/%s/delete/' % self.e1.id, {})
        self.assertEqual(json.loads(resp.data.decode('utf8')), {'deleted': 1})

        self.assertEqual(EModel.select().count(), 1)
        self.assertEqual(FModel.select().count(), 2)

        f_obj = FModel.get(id=self.f1.id)
        self.assertEqual(f_obj.e, None)

    def test_no_pagination_envelope(self):
        # EResource sets paginate_by=None; the list endpoint must still return
        # the {meta, objects} envelope (never a bare list), with everything on
        # a single page.
        resp = self.app.get('/api/emodel/')
        resp_json = self.response_json(resp)
        self.assertIsInstance(resp_json, dict)
        self.assertEqual(resp_json['objects'], [])
        self.assertEqual(resp_json['meta']['page'], 1)
        self.assertEqual(resp_json['meta']['page_count'], 0)

        emodels = [EModel.create(e_field='e%d' % i) for i in range(3)]
        resp = self.app.get('/api/emodel/?ordering=id')
        resp_json = self.response_json(resp)
        self.assertIsInstance(resp_json, dict)
        self.assertEqual(resp_json['meta']['page'], 1)
        self.assertEqual(resp_json['meta']['page_count'], 1)
        self.assertEqual(resp_json['meta']['next'], '')
        self.assertEqual([o['id'] for o in resp_json['objects']],
                         [e.id for e in emodels])

    def test_max_paginate_by_caps_limit(self):
        # EResource caps an explicit ?limit at max_paginate_by (5).
        for i in range(8):
            EModel.create(e_field='e%d' % i)
        resp = self.app.get('/api/emodel/?ordering=id&limit=100')
        resp_json = self.response_json(resp)
        self.assertEqual(len(resp_json['objects']), 5)
        self.assertEqual(resp_json['meta']['page_count'], 2)  # ceil(8 / 5)

    def test_nested_serialization_is_single_query(self):
        # listing rows with a nested chain (C -> b -> a) must not issue a
        # lookup per row -- the whole graph loads in one joined query.
        import logging
        for i in range(6):
            a = AModel.create(a_field='a%d' % i)
            b = BModel.create(a=a, b_field='b%d' % i)
            CModel.create(b=b, c_field='c%d' % i)

        count = {'n': 0}
        class H(logging.Handler):
            def emit(self, record):
                if record.getMessage().strip().upper().lstrip("(').").startswith('SELECT'):
                    count['n'] += 1
        logger = logging.getLogger('peewee')
        level, handler = logger.level, H()
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        try:
            resp = self.app.get('/api/cmodel/?ordering=id')
        finally:
            logger.removeHandler(handler)
            logger.setLevel(level)

        resp_json = self.response_json(resp)
        self.assertEqual(len(resp_json['objects']), 6)
        # nesting is present and correct...
        self.assertEqual(resp_json['objects'][0]['b']['a']['a_field'], 'a0')
        # ...and it cost a constant number of queries (a COUNT for pagination
        # plus one joined SELECT), not ~1 + 6*2 from lazy per-row loading.
        self.assertLessEqual(count['n'], 3)

    def test_nested_writes_disabled(self):
        # GResource sets nested_writes=False: a nested related dict is ignored
        # (never created), though the FK can still be set by scalar id.
        e1 = EModel.create(e_field='e1')
        emodel_count = EModel.select().count()

        resp = self.post_to('/api/gmodel/', {'g_field': 'g1',
                                             'e': {'e_field': 'sneaky'}})
        self.assertEqual(resp.status_code, 200)
        # the nested EModel was not created and the FK was left null
        self.assertEqual(EModel.select().count(), emodel_count)
        self.assertFalse(
            EModel.select().where(EModel.e_field == 'sneaky').exists())
        self.assertIsNone(GModel.get(g_field='g1').e)

        # a scalar foreign key still works
        resp = self.post_to('/api/gmodel/', {'g_field': 'g2', 'e': e1.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(GModel.get(g_field='g2').e, e1)


class RestApiValidationTestCase(RestApiTestCase):
    def setUp(self):
        super(RestApiValidationTestCase, self).setUp()
        # HModel is recreated fresh by the base setUp; clear the persistent
        # A-family rows (child tables first) so counts are predictable.
        for M in (DModel, CModel, BDetails, BModel, AModel):
            M.delete().execute()

    def test_resource_filter_fields_not_mutated(self):
        class ChildResource(RestResource):
            pass
        class ParentResource(RestResource):
            filter_fields = ['content', 'user']
            include_resources = {'user': ChildResource}

        before = list(ParentResource.filter_fields)
        ParentResource(RestAPI(self.flask_app), Message, Authentication())
        ParentResource(RestAPI(self.flask_app), Message, Authentication())
        self.assertEqual(ParentResource.filter_fields, before)

    def test_datetime_garbage_rejected(self):
        # unparseable date/time strings -> 400 naming the field, nothing
        # stored (previously the string was written to the database as-is).
        for field in ('h_date', 'h_day'):
            resp = self.post_to('/api/hmodel/', {'h_field': 'x',
                                                 field: 'not-a-date'})
            self.assertEqual(resp.status_code, 400)
            self.assertIn(field, self.response_json(resp)['error'])
        self.assertEqual(HModel.select().count(), 0)

    def test_datetime_formats_accepted(self):
        # ISO-8601 (what the serializer emits) round-trips.
        resp = self.post_to('/api/hmodel/', {'h_field': 'iso',
                                             'h_date': '2026-01-02T03:04:05'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(HModel.get(h_field='iso').h_date,
                         datetime.datetime(2026, 1, 2, 3, 4, 5))

        # peewee's own space-separated format is accepted too.
        resp = self.post_to('/api/hmodel/', {'h_field': 'pw',
                                             'h_date': '2026-01-02 03:04:05'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(HModel.get(h_field='pw').h_date,
                         datetime.datetime(2026, 1, 2, 3, 4, 5))

        # an empty string (e.g. a blank form input) means "no value".
        resp = self.post_to('/api/hmodel/', {'h_field': 'blank', 'h_date': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(HModel.get(h_field='blank').h_date)

    def test_unknown_fields_ignored_by_default(self):
        # default resources preserve the historical behavior: unrecognized
        # keys are silently ignored.
        resp = self.post_to('/api/amodel/', {'a_field': 'ok',
                                             'a_feild': 'typo'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(AModel.select().count(), 1)

    def test_reject_unknown_fields(self):
        # HResource opts in: a typo'd key -> 400 listing the offender.
        resp = self.post_to('/api/hmodel/', {'h_field': 'x',
                                             'h_feild': 'typo'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('h_feild', self.response_json(resp)['error'])
        self.assertEqual(HModel.select().count(), 0)

        resp = self.post_to('/api/hmodel/', {'h_field': 'clean'})
        self.assertEqual(resp.status_code, 200)

    def test_reject_unknown_fields_allows_fk_column_name(self):
        # writing the FK by column name ("a_id") is recognized, not rejected.
        a = AModel.create(a_field='a1')
        resp = self.post_to('/api/hmodel/', {'h_field': 'x', 'a_id': a.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(HModel.get(h_field='x').a, a)

    def test_reject_unknown_fields_blocks_pk(self):
        # strict mode 400s a "_pk" key like any other unknown, so the lenient
        # underscore guard is not the only thing standing between a payload and
        # a retargeted row.
        resp = self.post_to('/api/hmodel/', {'h_field': 'x', '_pk': 99})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('_pk', self.response_json(resp)['error'])
        self.assertEqual(HModel.select().count(), 0)

    def test_reject_unknown_filters(self):
        # HResource opts in: a query-string filter on an unknown field is a 400
        # naming the offender, not the full unfiltered collection.
        resp = self.app.get('/api/hmodel/?h_feild=x')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('h_feild', self.response_json(resp)['error'])

        # a real filter still works.
        resp = self.app.get('/api/hmodel/?h_field=clean')
        self.assertEqual(resp.status_code, 200)

    def test_unknown_filters_ignored_by_default(self):
        # a default resource stays lenient: an unknown filter is ignored, not a
        # 400, preserving the historical behavior.
        resp = self.app.get('/api/amodel/?bogus=x')
        self.assertEqual(resp.status_code, 200)

    def test_reject_unknown_fields_nested(self):
        # unknown keys inside a nested foreign-key dict are reported with the
        # __ path notation.
        resp = self.post_to('/api/hmodel/', {
            'h_field': 'x',
            'a': {'a_field': 'new', 'a_feild': 'typo'},
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn('a__a_feild', self.response_json(resp)['error'])

    def test_reject_unknown_fields_echo_roundtrip(self):
        # GET -> PUT of the same payload must not 400: the read-only pk is
        # stripped by scrub_readonly_fields, not treated as unknown.
        h = HModel.create(h_field='orig')
        resp = self.app.get('/api/hmodel/%s/' % h.id)
        data = self.response_json(resp)
        data['h_field'] = 'edited'

        resp = self.post_to('/api/hmodel/%s/' % h.id, data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(HModel.get(HModel.id == h.id).h_field, 'edited')

    def test_non_dict_body_rejected(self):
        # a JSON body that is not an object (list, string, number) is a 400.
        # Regression: a list used to raise AttributeError in the deserializer.
        for body in ([{'a_field': 'x'}], 'x', 3):
            resp = self.post_to('/api/amodel/', body)
            self.assertEqual(resp.status_code, 400)
            self.assertIn('JSON object', self.response_json(resp)['error'])
        self.assertEqual(AModel.select().count(), 0)

        # same on PUT to a detail url.
        a = AModel.create(a_field='a1')
        resp = self.app.put('/api/amodel/%s/' % a.id, data=json.dumps(['x']))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(AModel.get(id=a.id).a_field, 'a1')


class RestApiBulkTestCase(RestApiTestCase):
    def test_bulk_create(self):
        resp = self.post_to('/api/bulkitem/', [{'data': 'a'}, {'data': 'b'}])
        self.assertEqual(resp.status_code, 200)

        items = list(BulkItem.select().order_by(BulkItem.id))
        self.assertEqual([i.data for i in items], ['a', 'b'])
        self.assertEqual(self.response_json(resp), {'objects': [
            {'id': items[0].id, 'data': 'a', 'flag': False},
            {'id': items[1].id, 'data': 'b', 'flag': False},
        ]})

    def test_bulk_rolls_back_on_invalid_item(self):
        # the second item violates NOT NULL. The error names its index and the
        # first item's insert is rolled back.
        resp = self.post_to('/api/bulkitem/', [{'data': 'a'}, {}])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('index 1', self.response_json(resp)['error'])
        self.assertEqual(BulkItem.select().count(), 0)

        # a non-dict item is rejected the same way.
        resp = self.post_to('/api/bulkitem/', [{'data': 'a'}, 'x'])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('index 1', self.response_json(resp)['error'])
        self.assertEqual(BulkItem.select().count(), 0)

    def test_bulk_cap(self):
        # BulkItemResource sets max_bulk = 3.
        resp = self.post_to('/api/bulkitem/',
                            [{'data': str(i)} for i in range(4)])
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(BulkItem.select().count(), 0)

    def test_bulk_scrubs_readonly(self):
        # readonly_fields are stripped from every item, not just the first.
        resp = self.post_to('/api/bulkitem/', [
            {'data': 'a', 'flag': True},
            {'data': 'b', 'flag': True},
        ])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([i.flag for i in BulkItem.select()], [False, False])


class RestApiBasicTestCase(RestApiTestCase):
    def get_users_and_notes(self):
        users = self.create_users()

        notes = []
        for i in range(10):
            for user in users:
                notes.append(Note.create(user=user, message='%s-%s' % (user.username, i)))
        return users, notes

    def test_pagination(self):
        users, notes = self.get_users_and_notes()

        # do a simple list of the first 20 items
        resp = self.app.get('/api/note/?ordering=id')
        resp_json = self.response_json(resp)

        # verify we have page and link to next page
        self.assertEqual(resp_json['meta']['model'], 'note')
        self.assertEqual(resp_json['meta']['previous'], '')
        self.assertEqual(resp_json['meta']['page'], 1)
        self.assertEqual(resp_json['meta']['page_count'], 2)
        self.assertTrue('page=2' in resp_json['meta']['next'])

        # verify response objects are paginated properly
        self.assertAPINotes(resp_json, notes[:20])

        # do a list of first 10 items
        resp = self.app.get('/api/note/?ordering=id&limit=10')
        resp_json = self.response_json(resp)

        self.assertEqual(resp_json['meta']['model'], 'note')
        self.assertEqual(resp_json['meta']['previous'], '')
        self.assertEqual(resp_json['meta']['page'], 1)
        self.assertEqual(resp_json['meta']['page_count'], 3)
        self.assertTrue('page=2' in resp_json['meta']['next'])

        # verify response objects are paginated properly
        self.assertAPINotes(resp_json, notes[:10])

        # grab the second page
        resp = self.app.get(resp_json['meta']['next'])
        resp_json = self.response_json(resp)

        self.assertEqual(resp_json['meta']['model'], 'note')
        self.assertEqual(resp_json['meta']['page'], 2)
        self.assertEqual(resp_json['meta']['page_count'], 3)
        self.assertTrue('page=1' in resp_json['meta']['previous'])
        self.assertTrue('page=3' in resp_json['meta']['next'])

        # verify response objects are paginated properly
        self.assertAPINotes(resp_json, notes[10:20])

        # grab the last page
        resp = self.app.get(resp_json['meta']['next'])
        resp_json = self.response_json(resp)

        self.assertEqual(resp_json['meta']['model'], 'note')
        self.assertEqual(resp_json['meta']['next'], '')
        self.assertEqual(resp_json['meta']['page'], 3)
        self.assertTrue('page=2' in resp_json['meta']['previous'])

        # verify response objects are paginated properly
        self.assertAPINotes(resp_json, notes[20:])

    def test_limit_exceeds_default(self):
        # paginate_by is only a default page size, not a maximum: a client may
        # request a larger page via ?limit (there are 30 notes, default is 20).
        users, notes = self.get_users_and_notes()
        resp = self.app.get('/api/note/?ordering=id&limit=100')
        resp_json = self.response_json(resp)
        self.assertEqual(len(resp_json['objects']), len(notes))
        self.assertEqual(resp_json['meta']['page_count'], 1)

    def test_filtering(self):
        users, notes = self.get_users_and_notes()

        # do a simple filter on a related model
        resp = self.app.get('/api/note/?user=%s&ordering=id' % self.normal.id)
        resp_json = self.response_json(resp)

        self.assertAPIMeta(resp_json, {
            'model': 'note',
            'previous': '',
            'next': '',
            'page': 1,
            'page_count': 1,
        })
        self.assertAPINotes(resp_json, self.normal.note_set.order_by(Note.id))

        # do a filter following a join
        resp = self.app.get('/api/note/?user__username=admin&ordering=id')
        resp_json = self.response_json(resp)

        self.assertAPIMeta(resp_json, {
            'model': 'note',
            'previous': '',
            'next': '',
            'page': 1,
            'page_count': 1,
        })
        self.assertAPINotes(resp_json, self.admin.note_set.order_by(Note.id))

        # filter multiple fields
        notes = list(self.admin.note_set.order_by(Note.id))
        third_id = notes[3].id

        resp = self.app.get('/api/note/?user__username=admin&id__lt=%s&ordering=id' % third_id)
        resp_json = self.response_json(resp)
        self.assertAPINotes(resp_json, notes[:3])

        # do a filter using multiple values
        resp = self.app.get('/api/note/?user__username=admin&user__username=inactive&ordering=id')
        resp_json = self.response_json(resp)

        self.assertAPIMeta(resp_json, {
            'model': 'note',
            'previous': '',
            'next': '',
            'page': 1,
            'page_count': 1,
        })
        self.assertAPINotes(resp_json, Note.filter(user__in=[self.admin, self.inactive]).order_by(Note.id))

        # do a filter with a negation
        resp = self.app.get('/api/note/?-user__username=admin&ordering=id')
        resp_json = self.response_json(resp)
        self.assertAPINotes(resp_json, Note.filter(user__in=[
            self.normal, self.inactive]).order_by(Note.id))

        # do a filter with an IN operator and multiple IDs
        # https://github.com/coleifer/flask-peewee/issues/112
        resp = self.app.get('/api/note/?id__in=1,2,5')
        resp_json = self.response_json(resp)
        self.assertAPINotes(resp_json, Note.filter(id__in=[1,2,5]).order_by(Note.id))

        # repeated in params combine with comma-separated values. assert the
        # count too: assertAPINotes zips and would not notice a dropped id.
        resp = self.app.get('/api/note/?id__in=1,2&id__in=5')
        resp_json = self.response_json(resp)
        self.assertEqual(len(resp_json['objects']), 3)
        self.assertAPINotes(resp_json, Note.filter(id__in=[1,2,5]).order_by(Note.id))

        # also test that the IN operator works with list of strings
        resp = self.app.get('/api/user/?username__in=admin,normal')
        resp_json = self.response_json(resp)
        self.assertAPIUsers(resp_json, User.filter(username__in=['admin', 'normal']).order_by(User.id))

        for falsey in ('0', '', 'false', 'f'):
            resp = self.app.get('/api/user/?admin=%s' % falsey)
            resp_json = self.response_json(resp)
            self.assertAPIUsers(resp_json, User.filter(username='normal').order_by(User.id))

        resp = self.app.get('/api/user/?admin=true')
        resp_json = self.response_json(resp)
        self.assertAPIUsers(resp_json, User.filter(username='admin').order_by(User.id))

    def test_filter_with_pagination(self):
        users, notes = self.get_users_and_notes()
        notes = list(self.admin.note_set.order_by(Note.id))

        # do a simple filter on a related model
        resp = self.app.get('/api/note/?user__username=admin&limit=4&ordering=id')
        resp_json = self.response_json(resp)

        self.assertAPINotes(resp_json, notes[:4])

        next_url = resp_json['meta']['next']
        resp = self.app.get(next_url)
        resp_json = self.response_json(resp)

        self.assertAPINotes(resp_json, notes[4:8])

        next_url = resp_json['meta']['next']
        resp = self.app.get(next_url)
        resp_json = self.response_json(resp)

        self.assertEqual(resp_json['meta']['next'], '')
        self.assertAPINotes(resp_json, notes[8:])

        prev_url = resp_json['meta']['previous']
        resp = self.app.get(prev_url)
        resp_json = self.response_json(resp)

        self.assertAPINotes(resp_json, notes[4:8])

        prev_url = resp_json['meta']['previous']
        resp = self.app.get(prev_url)
        resp_json = self.response_json(resp)

        self.assertEqual(resp_json['meta']['previous'], '')
        self.assertAPINotes(resp_json, notes[:4])

    def test_filter_null(self):
        e1 = EModel.create(e_field='e1')
        f1 = FModel.create(e=e1, f_field='f1')
        f2 = FModel.create(f_field='f2')

        resp = self.app.get('/api/fmodel/?ordering=id')
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json['objects'], [
            {'id': f1.id, 'e': {'id': e1.id, 'e_field': 'e1'}, 'f_field': 'f1'},
            {'id': f2.id, 'e': None, 'f_field': 'f2'}])

        resp = self.app.get('/api/fmodel/?e__is=None')
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json['objects'], [
            {'id': f2.id, 'e': None, 'f_field': 'f2'}])

        resp = self.app.get('/api/fmodel/?-e__is=None')
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json['objects'], [
            {'id': f1.id, 'e': {'id': e1.id, 'e_field': 'e1'}, 'f_field': 'f1'}])

    def create_links(self):
        self.create_users()
        Link.create(src=self.admin, dst=self.normal, label='a-to-b')
        Link.create(src=self.normal, dst=self.admin, label='b-to-a')

    def test_filter_two_fks_same_model(self):
        # two foreign keys to one model must filter through separate aliased
        # joins, not collapse onto one join with contradictory predicates.
        self.create_links()
        resp = self.app.get('/api/link/?src__username=admin&dst__username=normal')
        resp_json = self.response_json(resp)
        self.assertEqual([o['label'] for o in resp_json['objects']], ['a-to-b'])

    def test_filter_one_path_shares_join(self):
        # two filters on one related path reuse a single aliased join, and a
        # boolean on the aliased path still converts through the real field.
        self.create_links()
        resource = api._registry[Link]
        with self.flask_app.test_request_context(
                '/api/link/?src__username=admin&src__active=True'):
            query = resource.process_query(resource.get_query())
        self.assertEqual(query.sql()[0].count('JOIN'), 1)
        self.assertEqual([l.label for l in query], ['a-to-b'])

    def test_filter_recursive_off_by_default(self):
        # related columns are not filterable unless listed in filter_fields.
        users = self.create_users()
        for user in users:
            self.create_message(user, user.username)

        # the message resource lists no user__ fields, so the password hash
        # cannot be tested one character at a time.
        resp = self.app.get('/api/message/?user__password__startswith=%s'
                            % self.admin.password[:6])
        self.assertEqual(len(self.response_json(resp)['objects']), 3)

        resp = self.app.get('/api/message/?user__username=admin')
        self.assertEqual(len(self.response_json(resp)['objects']), 3)

    def test_filter_recursive_opt_in(self):
        # NoteResource sets filter_recursive, so every user column is filterable
        # under user__.
        users = self.create_users()
        for user in users:
            Note.create(user=user, message=user.username)

        resp = self.app.get('/api/note/?user__password__startswith=%s'
                            % self.admin.password[:6])
        self.assertEqual(len(self.response_json(resp)['objects']), 3)

        resp = self.app.get('/api/note/?user__password__startswith=nomatch')
        self.assertEqual(len(self.response_json(resp)['objects']), 0)

    def test_nested_resource_filters_require_declaration(self):
        # a nested resource without filter_fields adds no filters to the parent.
        class BareUser(RestResource):
            pass
        class DeclaredUser(RestResource):
            filter_fields = ('username',)
        class WithBare(RestResource):
            include_resources = {'user': BareUser}
        class WithDeclared(RestResource):
            include_resources = {'user': DeclaredUser}

        bare = WithBare(api, Comment, Authentication())
        self.assertEqual([f for f in bare._filter_fields if '__' in f], [])
        self.assertEqual(bare._field_tree.children['user'].fields, [])

        declared = WithDeclared(api, Comment, Authentication())
        self.assertEqual([f for f in declared._filter_fields if '__' in f],
                         ['user__username'])
        self.assertEqual(
            [f.name for f in declared._field_tree.children['user'].fields],
            ['username'])

    def test_page_out_of_range(self):
        # ?page= past the end is clamped to the last page instead of
        # overflowing the OFFSET.
        self.get_users_and_notes()

        resp = self.app.get('/api/note/?page=99999999999999999999&limit=10')
        self.assertEqual(resp.status_code, 200)
        resp_json = self.response_json(resp)
        self.assertEqual(resp_json['meta']['page'],
                         resp_json['meta']['page_count'])
        self.assertTrue(len(resp_json['objects']) > 0)

    def test_filter_negated_related(self):
        # negation survives the rebind onto the aliased field.
        self.create_links()
        resp = self.app.get('/api/link/?-src__username=admin')
        resp_json = self.response_json(resp)
        self.assertEqual([o['label'] for o in resp_json['objects']], ['b-to-a'])

    def test_negated_filter_multiple_values(self):
        # two negated values of one field exclude both. the old code built
        # NOT a OR NOT b, which matched every row.
        users = self.create_users()
        for u in users:
            Note.create(user=u, message=u.username)
        resp = self.app.get('/api/note/?-user__username=admin'
                            '&-user__username=normal&ordering=id')
        resp_json = self.response_json(resp)
        self.assertEqual([o['message'] for o in resp_json['objects']],
                         ['inactive'])

    def test_ne_filter_multiple_values(self):
        # ne is an exclusion too, so repeated values AND even without the "-"
        # prefix: id != a AND id != b, not the vacuous OR.
        users = self.create_users()
        notes = [Note.create(user=u, message=u.username) for u in users]
        ids = [n.id for n in notes]
        resp = self.app.get('/api/note/?id__ne=%s&id__ne=%s&ordering=id'
                            % (ids[0], ids[1]))
        resp_json = self.response_json(resp)
        self.assertEqual([o['id'] for o in resp_json['objects']], [ids[2]])

    def test_not_in_filter(self):
        # not_in splits comma-separated values exactly like in. it used to
        # bind the whole string as a single value and match every row.
        users = self.create_users()
        notes = [Note.create(user=u, message=u.username) for u in users]
        ids = [n.id for n in notes]
        resp = self.app.get('/api/note/?id__not_in=%s,%s&ordering=id'
                            % (ids[0], ids[1]))
        resp_json = self.response_json(resp)
        self.assertEqual([o['id'] for o in resp_json['objects']], [ids[2]])

        resp = self.app.get('/api/note/?id__not_in=%s&id__not_in=%s&ordering=id'
                            % (ids[0], ids[1]))
        resp_json = self.response_json(resp)
        self.assertEqual([o['id'] for o in resp_json['objects']], [ids[2]])

    def test_between_filter(self):
        # between takes two comma-separated bounds, inclusive. a malformed
        # value is a 400, not an uncaught TypeError.
        users = self.create_users()
        notes = [Note.create(user=users[0], message=str(i)) for i in range(5)]
        ids = [n.id for n in notes]
        resp = self.app.get('/api/note/?id__between=%s,%s&ordering=id'
                            % (ids[1], ids[3]))
        resp_json = self.response_json(resp)
        self.assertEqual([o['id'] for o in resp_json['objects']], ids[1:4])

        resp = self.app.get('/api/note/?-id__between=%s,%s&ordering=id'
                            % (ids[1], ids[3]))
        resp_json = self.response_json(resp)
        self.assertEqual([o['id'] for o in resp_json['objects']],
                         [ids[0], ids[4]])

        resp = self.app.get('/api/note/?id__between=%s' % ids[1])
        self.assertEqual(resp.status_code, 400)

    def test_serialize_two_relations_one_model(self):
        # two relations to one model each get their own path-keyed field set:
        # one cannot leak the other's fields, and nesting one does not nest the
        # other. before, both shared _fields keyed by the User class.
        self.create_users()
        Link.create(src=self.admin, dst=self.normal, label='x')
        link = Link.get(Link.label == 'x')

        class PublicUser(RestResource):
            fields = ('id', 'username')

        class FullUser(RestResource):
            fields = ('id', 'username', 'email')

        class BothResource(RestResource):
            include_resources = {'src': PublicUser, 'dst': FullUser}

        out = BothResource(api, Link, Authentication()).serialize_object(link)
        self.assertEqual(out['src'], {'id': self.admin.id, 'username': 'admin'})
        self.assertEqual(set(out['dst']), {'id', 'username', 'email'})

        class SrcOnly(RestResource):
            include_resources = {'src': PublicUser}

        out2 = SrcOnly(api, Link, Authentication()).serialize_object(link)
        # the undeclared sibling relation stays a scalar id, not a nested dict.
        self.assertEqual(out2['dst'], self.normal.id)


class RestApiErrorsTestCase(RestApiTestCase):
    def assertJSONError(self, resp, status, message):
        self.assertEqual(resp.status_code, status)
        self.assertEqual(resp.content_type, 'application/json')
        self.assertEqual(self.response_json(resp), {'error': message})

    def test_missing_object(self):
        resp = self.app.get('/api/note/1/')
        self.assertJSONError(resp, 404, 'Not found')

    def test_bad_method(self):
        resp = self.app.get('/api/note/1/delete/')
        self.assertJSONError(resp, 405, 'Unsupported method "GET"')

    def test_auth_failed(self):
        resp = self.app.post('/api/note/', data='{}')
        self.assertJSONError(resp, 401, 'Authentication failed')
        self.assertEqual(resp.headers['WWW-Authenticate'],
                         'Basic realm="Login Required"')


class RestApiUserAuthTestCase(RestApiTestCase):
    def setUp(self):
        super(RestApiUserAuthTestCase, self).setUp()
        self.create_users()

    def create_notes(self):
        notes = [
            Note.create(user=self.admin, message='admin'),
            Note.create(user=self.normal, message='normal'),
        ]
        self.admin_note, self.normal_note = notes
        return notes

    def test_list_get(self):
        resp = self.app.get('/api/note/')
        resp_json = self.response_json(resp)

        self.assertAPIResponse(resp_json, [])
        self.assertAPIMeta(resp_json, {
            'model': 'note',
            'next': '',
            'page': 1,
            'page_count': 0,
            'previous': ''})

        self.create_notes()

        resp = self.app.get('/api/note/?ordering=id')
        resp_json = self.response_json(resp)

        self.assertAPINotes(resp_json, [
            self.admin_note,
            self.normal_note,
        ])

    def test_detail_get(self):
        resp = self.app.get('/api/note/1/')
        self.assertEqual(resp.status_code, 404)

        self.create_notes()

        resp = self.app.get('/api/note/%s/' % self.normal_note.id)
        resp_json = self.response_json(resp)
        self.assertAPINote(resp_json, self.normal_note)

    def test_auth_create(self):
        note_data = {'message': 'test', 'user': self.inactive.id}
        serialized = json.dumps(note_data)

        # this request is not authorized
        resp = self.app.post('/api/note/', data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized, but user does not exist in database
        resp = self.app.post('/api/note/', data=serialized, headers=self.auth_headers('xxx', 'xxx'))
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database
        resp = self.app.post('/api/note/', data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

    def test_create(self):
        note_data = {'message': 'test', 'user': self.inactive.id}
        serialized = json.dumps(note_data)

        # authorized as an admin
        resp = self.app.post('/api/note/', data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

        new_note = Note.get(message='test')
        self.assertEqual(new_note.user, self.inactive)

        resp_json = self.response_json(resp)
        self.assertAPINote(resp_json, new_note)

        note_data = {'message': 'test2', 'user': self.inactive.id,
                     'created_date': '2026-01-02T03:04:05'}
        resp = self.app.post('/api/note/', data=json.dumps(note_data),
                             headers=self.auth_headers('normal', 'normal'))
        new_note = Note.get(message='test2')
        self.assertEqual(new_note.user, self.inactive)
        self.assertEqual(new_note.created_date,
                         datetime.datetime(2026, 1, 2, 3, 4, 5))

        resp_json = self.response_json(resp)
        self.assertEqual(resp_json, {
            'message': 'test2', 'user': self.inactive.id, 'id': new_note.id,
            'created_date': '2026-01-02T03:04:05'})

    def test_auth_edit(self):
        self.create_notes()

        note_data = {'message': 'edited'}
        serialized = json.dumps(note_data)

        url = '/api/note/%s/' % self.admin_note.id

        # this request is not authorized
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized, but user does not exist in database
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('xxx', 'xxx'))
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

    def test_edit(self):
        self.create_notes()

        note_data = {'message': 'edited'}
        serialized = json.dumps(note_data)

        url = '/api/note/%s/' % self.admin_note.id

        # authorized as an admin
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

        note = Note.get(id=self.admin_note.id)
        self.assertEqual(note.message, 'edited')

        resp_json = self.response_json(resp)
        self.assertAPINote(resp_json, note)

    def test_auth_patch(self):
        # PATCH is a protected method like PUT.
        self.create_notes()

        serialized = json.dumps({'message': 'patched'})
        url = '/api/note/%s/' % self.admin_note.id

        resp = self.app.patch(url, data=serialized)
        self.assertEqual(resp.status_code, 401)

        resp = self.app.patch(url, data=serialized,
                              headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Note.get(id=self.admin_note.id).message, 'patched')

    def test_readonly_field_mass_assignment(self):
        # UserResource marks "admin" read-only; an authorized editor still
        # cannot escalate a user's privileges through the request body.
        url = '/api/user/%s/' % self.normal.id
        serialized = json.dumps({'username': 'normal', 'admin': True})

        resp = self.app.put(url, data=serialized,
                            headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.get(User.id == self.normal.id).admin)

    def test_readonly_pk_immutable(self):
        # the primary key is always read-only and can't be rewritten.
        url = '/api/user/%s/' % self.normal.id
        serialized = json.dumps({'username': 'normal', 'id': 99999})

        resp = self.app.put(url, data=serialized,
                            headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.select().where(User.id == self.normal.id).exists())
        self.assertFalse(User.select().where(User.id == 99999).exists())

    def test_write_pk_payload_ignored(self):
        # a "_pk" in the body must not retarget the row, even on a lenient
        # (default) resource. The addressed row is the only one a write may
        # touch. Before the underscore guard a PUT edited a different row and a
        # POST clobbered one via update-instead-of-insert.
        self.create_notes()

        # PUT at admin_note carrying normal_note's pk edits admin_note only.
        url = '/api/note/%s/' % self.admin_note.id
        body = json.dumps({'message': 'edited', '_pk': self.normal_note.id})
        resp = self.app.put(url, data=body,
                            headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Note.get(id=self.admin_note.id).message, 'edited')
        self.assertEqual(Note.get(id=self.normal_note.id).message, 'normal')

        # POST carrying an existing pk inserts a new row, leaving it untouched.
        before = Note.select().count()
        body = json.dumps({'message': 'created', 'user': self.normal.id,
                           '_pk': self.admin_note.id})
        resp = self.app.post('/api/note/', data=body,
                             headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Note.select().count(), before + 1)
        self.assertEqual(Note.get(id=self.admin_note.id).message, 'edited')

    def test_write_fk_by_column_name(self):
        # a foreign key may still be written by its column name ("user_id"),
        # the legitimate use of the unknown-key fallback the _pk guard keeps.
        body = json.dumps({'message': 'via-column', 'user_id': self.inactive.id})
        resp = self.app.post('/api/note/', data=body,
                             headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Note.get(message='via-column').user, self.inactive)

    def test_nested_readonly_mass_assignment_edit(self):
        # A read-only field on a *nested* resource must be honored just like on
        # a top-level one. A non-admin edits their own comment and tries to flip
        # their user's "admin" flag through the nested user payload -- it must
        # not take effect, even though the same user could not write to the
        # admin-only /api/user/ endpoint directly.
        comment = Comment.create(user=self.normal, body='hi')
        url = '/api/comment/%s/' % comment.id
        serialized = json.dumps({'body': 'edited', 'user': {'admin': True}})

        resp = self.app.put(url, data=serialized,
                            headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)
        # escalation blocked...
        self.assertFalse(User.get(User.id == self.normal.id).admin)
        # ...but the legitimate part of the write still applied.
        self.assertEqual(Comment.get(Comment.id == comment.id).body, 'edited')

    def test_nested_readonly_mass_assignment_create(self):
        # Creating a parent with a nested new user must not let a non-admin
        # smuggle in a privileged ("admin": true) user via the nested payload.
        admin_before = User.select().where(User.admin == True).count()
        serialized = json.dumps({
            'body': 'x',
            'user': {'username': 'sneaky', 'password': 'x', 'email': '',
                     'admin': True}})

        resp = self.app.post('/api/comment/', data=serialized,
                             headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

        # whether or not a nested user is created, none may be an admin.
        sneaky = User.get_or_none(User.username == 'sneaky')
        if sneaky is not None:
            self.assertFalse(sneaky.admin)
        self.assertEqual(
            User.select().where(User.admin == True).count(), admin_before)

    def test_filter_join_with_nested_serialization(self):
        # a filter that joins a related table (DQ-based) must compose with the
        # aliased eager-load join used for nested serialization -- both join
        # the user table, and they must not collide.
        Comment.create(user=self.admin, body='by admin')
        Comment.create(user=self.normal, body='by normal')

        resp = self.app.get('/api/comment/?user__username=admin&ordering=id')
        resp_json = self.response_json(resp)
        self.assertEqual(len(resp_json['objects']), 1)
        obj = resp_json['objects'][0]
        self.assertEqual(obj['body'], 'by admin')
        # nested user hydrated from the aliased join, not a per-row lookup
        self.assertEqual(obj['user']['username'], 'admin')
        self.assertEqual(obj['user']['id'], self.admin.id)

    def test_nested_check_forbids_unauthorized_create(self):
        # PingResource nests AdminOnlyUserResource, which requires an admin for
        # user writes. A non-admin is authorized to create pings, but the
        # nested user write must be rejected (403) and roll back the request.
        ping_before = Ping.select().count()
        user_before = User.select().count()
        serialized = json.dumps({'body': 'x',
                                 'user': {'username': 'sneaky', 'password': 'x',
                                          'email': '', 'admin': True}})
        resp = self.app.post('/api/ping/', data=serialized,
                             headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 403)
        # rolled back: neither the nested user nor the ping was created.
        self.assertEqual(User.select().count(), user_before)
        self.assertEqual(Ping.select().count(), ping_before)

    def test_nested_check_forbids_unauthorized_edit(self):
        ping = Ping.create(user=self.normal, body='hi')
        serialized = json.dumps({'user': {'username': 'changed'}})
        resp = self.app.put('/api/ping/%s/' % ping.id, data=serialized,
                            headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(User.get(User.id == self.normal.id).username, 'normal')

    def test_nested_check_allows_admin(self):
        # an admin satisfies the child check, so the nested user is created
        # (with read-only fields still stripped).
        serialized = json.dumps({'body': 'x',
                                 'user': {'username': 'made', 'password': 'x',
                                          'email': '', 'admin': True}})
        resp = self.app.post('/api/ping/', data=serialized,
                             headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 200)
        made = User.get(User.username == 'made')
        self.assertFalse(made.admin)

    def test_nested_write_rolls_back_on_parent_error(self):
        # the nested user save and the parent save share a transaction: when
        # the parent insert fails (missing required "body"), the already-saved
        # nested user must be rolled back too rather than left orphaned.
        user_before = User.select().count()
        serialized = json.dumps({'user': {'username': 'orphan',
                                          'password': 'x', 'email': ''}})
        resp = self.app.post('/api/ping/', data=serialized,
                             headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(User.select().count(), user_before)
        self.assertFalse(
            User.select().where(User.username == 'orphan').exists())

    def test_auth_delete(self):
        self.create_notes()

        url = '/api/note/%s/' % self.admin_note.id

        # this request is not authorized
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 401)

        # authorized, but user does not exist in database
        resp = self.app.delete(url, headers=self.auth_headers('xxx', 'xxx'))
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database
        resp = self.app.delete(url, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

    def test_delete(self):
        self.create_notes()

        url = '/api/note/%s/' % self.admin_note.id

        # authorized as an admin
        resp = self.app.delete(url, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(Note.select().count(), 1)

        resp_json = self.response_json(resp)
        self.assertEqual(resp_json, {'deleted': 1})


class RestApiOwnerAuthTestCase(RestApiTestCase):
    def setUp(self):
        super(RestApiOwnerAuthTestCase, self).setUp()
        self.create_users()

    def create_messages(self):
        messages = [
            Message.create(user=self.admin, content='admin'),
            Message.create(user=self.normal, content='normal'),
        ]
        self.admin_message, self.normal_message = messages
        return messages

    def test_list_get(self):
        resp = self.app.get('/api/message/')
        resp_json = self.response_json(resp)

        self.assertAPIResponse(resp_json, [])
        self.assertAPIMeta(resp_json, {
            'model': 'message',
            'next': '',
            'page': 1,
            'page_count': 0,
            'previous': ''})

        self.create_messages()

        resp = self.app.get('/api/message/?ordering=id')
        resp_json = self.response_json(resp)

        self.assertAPIMessages(resp_json, [
            self.admin_message,
            self.normal_message,
        ])

    def test_detail_get(self):
        resp = self.app.get('/api/message/1/')
        self.assertEqual(resp.status_code, 404)

        self.create_messages()

        resp = self.app.get('/api/message/%s/' % self.normal_message.id)
        resp_json = self.response_json(resp)
        self.assertAPIMessage(resp_json, self.normal_message)

    def test_auth_create(self):
        message_data = {'content': 'test'}
        serialized = json.dumps(message_data)

        # this request is not authorized
        resp = self.app.post('/api/message/', data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized, but user does not exist in database
        resp = self.app.post('/api/message/', data=serialized, headers=self.auth_headers('xxx', 'xxx'))
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database
        resp = self.app.post('/api/message/', data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

    def test_create(self):
        message_data = {'content': 'test'}
        serialized = json.dumps(message_data)

        # authorized as an admin
        resp = self.app.post('/api/message/', data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

        new_message = Message.get(content='test')
        self.assertEqual(new_message.user, self.normal)

        resp_json = self.response_json(resp)
        self.assertAPIMessage(resp_json, new_message)

    def test_auth_edit(self):
        self.create_messages()

        message_data = {'content': 'edited'}
        serialized = json.dumps(message_data)

        url = '/api/message/%s/' % self.normal_message.id

        # this request is not authorized
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized, but user does not exist in database
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('xxx', 'xxx'))
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database, but not owner
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 403)

        # authorized, user in database, is owner
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

        obj = Message.get(id=self.normal_message.id)
        self.assertEqual(obj.content, 'edited')

    def test_edit(self):
        self.create_messages()

        message_data = {'content': 'edited'}
        serialized = json.dumps(message_data)

        url = '/api/message/%s/' % self.normal_message.id

        # authorized as normal
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

        message = Message.get(id=self.normal_message.id)
        self.assertEqual(message.content, 'edited')

        resp_json = self.response_json(resp)
        self.assertAPIMessage(resp_json, message)

    def test_auth_patch(self):
        # PATCH must clear the same owner check as PUT.
        self.create_messages()

        serialized = json.dumps({'content': 'patched'})
        url = '/api/message/%s/' % self.normal_message.id

        resp = self.app.patch(url, data=serialized,
                              headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 403)

        resp = self.app.patch(url, data=serialized,
                              headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Message.get(id=self.normal_message.id).content,
                         'patched')

    def test_auth_edit_via_post(self):
        # a POST to a detail url is an edit, so it must clear the owner check
        # like PUT. Regression: a non-owner POST used to overwrite the row and
        # reassign its owner to the caller.
        self.create_messages()

        original = self.normal_message.content
        url = '/api/message/%s/' % self.normal_message.id

        # a non-owner POST is forbidden and changes nothing.
        resp = self.app.post(url, data=json.dumps({'content': 'hacked'}),
                             headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 403)
        obj = Message.get(id=self.normal_message.id)
        self.assertEqual(obj.content, original)
        self.assertEqual(obj.user_id, self.normal.id)

        # the owner can still edit through POST.
        resp = self.app.post(url, data=json.dumps({'content': 'edited'}),
                             headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)
        obj = Message.get(id=self.normal_message.id)
        self.assertEqual(obj.content, 'edited')
        self.assertEqual(obj.user_id, self.normal.id)

    def test_auth_delete(self):
        self.create_messages()

        url = '/api/message/%s/' % self.normal_message.id

        # this request is not authorized
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 401)

        # authorized, but user does not exist in database
        resp = self.app.delete(url, headers=self.auth_headers('xxx', 'xxx'))
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database, not owner
        resp = self.app.delete(url, headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 403)

        # authorized, user in database, is owner
        resp = self.app.delete(url, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

    def test_delete(self):
        self.create_messages()

        url = '/api/message/%s/' % self.normal_message.id

        # authorized as an admin
        resp = self.app.delete(url, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(Message.select().count(), 1)

        resp_json = self.response_json(resp)
        self.assertEqual(resp_json, {'deleted': 1})


class RestApiAdminAuthTestCase(RestApiTestCase):
    def test_list_get(self):
        resp = self.app.get('/api/user/')
        resp_json = self.response_json(resp)

        self.assertAPIResponse(resp_json, [])
        self.assertAPIMeta(resp_json, {
            'model': 'user',
            'next': '',
            'page': 1,
            'page_count': 0,
            'previous': ''})

        self.create_users()

        resp = self.app.get('/api/user/?ordering=id')
        resp_json = self.response_json(resp)

        self.assertAPIUsers(resp_json, [
            self.admin,
            self.normal,
        ])

        resp = self.app.get('/api/user/?admin=True')
        self.assertAPIUsers(self.response_json(resp), [self.admin])

        resp = self.app.get('/api/user/?admin=False')
        self.assertAPIUsers(self.response_json(resp), [self.normal])

    def test_detail_get(self):
        resp = self.app.get('/api/user/1/')
        self.assertEqual(resp.status_code, 404)

        self.create_users()

        resp = self.app.get('/api/user/%s/' % self.normal.id)
        resp_json = self.response_json(resp)
        self.assertAPIUser(resp_json, self.normal)

        resp = self.app.get('/api/user/%s/' % self.inactive.id)
        self.assertEqual(resp.status_code, 404)

    def test_auth_create(self):
        self.create_users()

        new_pass = make_password('test')

        user_data = {'username': 'test', 'password': new_pass, 'email': ''}
        serialized = json.dumps(user_data)

        # this request is not authorized
        resp = self.app.post('/api/user/', data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized, but user does not exist in database
        resp = self.app.post('/api/user/', data=serialized, headers=self.auth_headers('xxx', 'xxx'))
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database, but not an administrator
        resp = self.app.post('/api/user/', data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 401)

        # authorized as an admin
        resp = self.app.post('/api/user/', data=serialized, headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 200)

    def test_create(self):
        self.create_users()

        new_pass = make_password('test')

        user_data = {'username': 'test', 'password': new_pass, 'email': ''}
        serialized = json.dumps(user_data)

        # authorized as an admin
        resp = self.app.post('/api/user/', data=serialized, headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 200)

        new_user = User.get(username='test')
        self.assertTrue(check_password('test', new_user.password))

        resp_json = self.response_json(resp)
        self.assertAPIUser(resp_json, new_user)

    def test_auth_edit(self):
        self.create_users()

        user_data = {'username': 'edited'}
        serialized = json.dumps(user_data)

        url = '/api/user/%s/' % self.normal.id

        # this request is not authorized
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized, but user does not exist in database
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('xxx', 'xxx'))
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database, but not an administrator
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 401)

        # authorized as an admin
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 200)

    def test_edit(self):
        self.create_users()

        user_data = {'username': 'edited'}
        serialized = json.dumps(user_data)

        url = '/api/user/%s/' % self.normal.id

        # authorized as an admin
        resp = self.app.put(url, data=serialized, headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 200)

        user = User.get(id=self.normal.id)
        self.assertEqual(user.username, 'edited')

        resp_json = self.response_json(resp)
        self.assertAPIUser(resp_json, user)

    def test_auth_delete(self):
        self.create_users()

        url = '/api/user/%s/' % self.normal.id

        # this request is not authorized
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 401)

        # authorized, but user does not exist in database
        resp = self.app.delete(url, headers=self.auth_headers('xxx', 'xxx'))
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database, but not an administrator
        resp = self.app.delete(url, headers=self.auth_headers('normal', 'normal'))
        self.assertEqual(resp.status_code, 401)

        # authorized as an admin
        resp = self.app.delete(url, headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 200)

    def test_delete(self):
        self.create_users()

        url = '/api/user/%s/' % self.normal.id

        # authorized as an admin
        resp = self.app.delete(url, headers=self.auth_headers('admin', 'admin'))
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(User.select().count(), 2)

        resp_json = self.response_json(resp)
        self.assertEqual(resp_json, {'deleted': 1})


class RestApiKeyAuthTestCase(RestApiTestCase):
    def setUp(self):
        super(RestApiKeyAuthTestCase, self).setUp()

        self.tm1 = TestModel.create(data='test1')
        self.tm2 = TestModel.create(data='test2')

        self.k1 = APIKey.create(key='k', secret='s')
        self.k2 = APIKey.create(key='k2', secret='s2')

    def test_list_get(self):
        with self.flask_app.test_client() as c:
            resp = c.get('/api/testmodel/')
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.api_key, None)

            resp = c.get('/api/testmodel/?key=k&secret=s2')
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.api_key, None)

            resp = c.get('/api/testmodel/?key=k&secret=s')
            self.assertEqual(g.api_key, self.k1)
            resp_json = self.response_json(resp)

            self.assertAPITestModels(resp_json, [
                self.tm1,
                self.tm2,
            ])
            self.assertAPIMeta(resp_json, {
                'model': 'testmodel',
                'next': '',
                'page': 1,
                'page_count': 1,
                'previous': ''})

    def test_auth_headers(self):
        with self.flask_app.test_client() as c:
            resp = c.get('/api/testmodel/', headers={'key': 'k', 'secret': 'foo'})
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.api_key, None)

            resp = c.get('/api/testmodel/', headers={'key': 'k', 'secret': 's'})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(g.api_key, self.k1)

    def test_create(self):
        with self.flask_app.test_client() as c:
            test_data = {'data': 't3'}
            serialized = json.dumps(test_data)

            resp = c.post('/api/testmodel/', data=serialized)
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.api_key, None)

            resp = c.post('/api/testmodel/?key=k&secret=s2', data=serialized)
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.api_key, None)

            # test passing in via get args
            resp = c.post('/api/testmodel/?key=k&secret=s', data=serialized)
            self.assertEqual(g.api_key, self.k1)
            resp_json = self.response_json(resp)

            self.assertEqual(TestModel.select().count(), 3)
            self.assertEqual(resp_json['data'], 't3')

            resp = c.post('/api/testmodel/', data={
                'data': json.dumps({'data': 't4'}),
                'key': 'k',
                'secret': 's'})
            self.assertEqual(g.api_key, self.k1)
            resp_json = self.response_json(resp)

            self.assertEqual(TestModel.select().count(), 4)
            self.assertEqual(resp_json['data'], 't4')


class RestApiBearerAuthTestCase(RestApiTestCase):
    def setUp(self):
        super(RestApiBearerAuthTestCase, self).setUp()
        self.doc = BearerDoc.create(data='d1')
        # BearerDoc is protected by a bearer auth over APIKey.key, so an
        # APIKey row's "key" value is the bearer token.
        self.k1 = APIKey.create(key='tok', secret='s')

    def test_missing_token(self):
        with self.flask_app.test_client() as c:
            resp = c.get('/api/bearerdoc/')
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.api_key, None)

    def test_bad_scheme_or_token(self):
        with self.flask_app.test_client() as c:
            # wrong scheme (basic) is not accepted as a bearer token
            resp = c.get('/api/bearerdoc/', headers={'Authorization': 'Basic tok'})
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.api_key, None)

            # unknown token
            resp = c.get('/api/bearerdoc/', headers=self.bearer('nope'))
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.api_key, None)

    def test_valid_token(self):
        with self.flask_app.test_client() as c:
            resp = c.get('/api/bearerdoc/', headers=self.bearer('tok'))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(g.api_key, self.k1)
            resp_json = self.response_json(resp)
            self.assertEqual([o['data'] for o in resp_json['objects']], ['d1'])

    def test_create_with_token(self):
        with self.flask_app.test_client() as c:
            resp = c.post('/api/bearerdoc/', data=json.dumps({'data': 'd2'}),
                          headers=self.bearer('tok'))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(g.api_key, self.k1)
            self.assertEqual(BearerDoc.select().count(), 2)

            # without the token the write is rejected
            resp = c.post('/api/bearerdoc/', data=json.dumps({'data': 'd3'}))
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(BearerDoc.select().count(), 2)


class RestApiUserBearerAuthTestCase(RestApiTestCase):
    def setUp(self):
        super(RestApiUserBearerAuthTestCase, self).setUp()
        self.create_users()
        # Tweet is owner-restricted and protected by a user-resolving bearer
        # auth over ApiToken, so a token maps to (and authenticates as) a user.
        ApiToken.create(token='ntok', user=self.normal)
        ApiToken.create(token='atok', user=self.admin)

    def test_token_resolves_to_user_and_sets_owner(self):
        with self.flask_app.test_client() as c:
            resp = c.post('/api/tweet/', data=json.dumps({'content': 'hi'}),
                          headers=self.bearer('ntok'))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(g.user, self.normal)
            # RestrictOwnerResource assigned the owner from the token's user
            self.assertEqual(Tweet.get(content='hi').user, self.normal)

    def test_missing_or_bad_token(self):
        with self.flask_app.test_client() as c:
            resp = c.post('/api/tweet/', data=json.dumps({'content': 'x'}))
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.user, None)

            resp = c.post('/api/tweet/', data=json.dumps({'content': 'x'}),
                          headers=self.bearer('nope'))
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(Tweet.select().count(), 0)

    def test_bulk_create_stamps_owner(self):
        # TweetResource allows bulk. save_object stamps each created row with
        # the authenticated user.
        resp = self.app.post('/api/tweet/',
                             data=json.dumps([{'content': 'a'},
                                              {'content': 'b'}]),
                             headers=self.bearer('ntok'))
        self.assertEqual(resp.status_code, 200)

        tweets = list(Tweet.select().order_by(Tweet.id))
        self.assertEqual([t.content for t in tweets], ['a', 'b'])
        self.assertEqual([t.user for t in tweets], [self.normal, self.normal])

    def test_owner_restriction_via_token(self):
        # a tweet owned by normal; admin's token is a different user and must
        # not be able to edit it, while normal's token can.
        tweet = Tweet.create(user=self.normal, content='orig')
        with self.flask_app.test_client() as c:
            resp = c.put('/api/tweet/%s/' % tweet.id,
                         data=json.dumps({'content': 'hax'}),
                         headers=self.bearer('atok'))
            self.assertEqual(resp.status_code, 403)

            resp = c.put('/api/tweet/%s/' % tweet.id,
                         data=json.dumps({'content': 'edit'}),
                         headers=self.bearer('ntok'))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(Tweet.get(id=tweet.id).content, 'edit')


class RestApiHashedBearerAuthTestCase(RestApiTestCase):
    def setUp(self):
        super(RestApiHashedBearerAuthTestCase, self).setUp()
        self.create_users()
        # HashedDoc is owner-restricted and protected (all methods) by a
        # hashed bearer auth over HashedToken, made by make_token_model.
        self.token, self.raw = HashedToken.create_token(user=self.normal)

    def test_only_hash_stored(self):
        db_token = HashedToken.get(HashedToken.id == self.token.id)
        self.assertEqual(
            db_token.token_hash,
            hashlib.sha256(self.raw.encode('utf-8')).hexdigest())
        self.assertNotEqual(db_token.token_hash, self.raw)

    def test_valid_token(self):
        with self.flask_app.test_client() as c:
            resp = c.get('/api/hasheddoc/', headers=self.bearer(self.raw))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(g.api_key, self.token)
            self.assertEqual(g.user, self.normal)

    def test_bad_token(self):
        with self.flask_app.test_client() as c:
            resp = c.get('/api/hasheddoc/', headers=self.bearer('nope'))
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(g.user, None)

            # the stored hash is not itself a valid token
            resp = c.get('/api/hasheddoc/',
                         headers=self.bearer(self.token.token_hash))
            self.assertEqual(resp.status_code, 401)

    def test_revoked_token(self):
        self.token.revoked = True
        self.token.save()
        with self.flask_app.test_client() as c:
            resp = c.get('/api/hasheddoc/', headers=self.bearer(self.raw))
            self.assertEqual(resp.status_code, 401)

    def test_expiry(self):
        day = datetime.timedelta(days=1)
        _, live = HashedToken.create_token(
            user=self.normal, expires=datetime.datetime.now() + day)
        _, dead = HashedToken.create_token(
            user=self.normal, expires=datetime.datetime.now() - day)

        with self.flask_app.test_client() as c:
            resp = c.get('/api/hasheddoc/', headers=self.bearer(live))
            self.assertEqual(resp.status_code, 200)

            resp = c.get('/api/hasheddoc/', headers=self.bearer(dead))
            self.assertEqual(resp.status_code, 401)

            # null expiry never expires
            resp = c.get('/api/hasheddoc/', headers=self.bearer(self.raw))
            self.assertEqual(resp.status_code, 200)

    def test_token_user_sets_owner(self):
        with self.flask_app.test_client() as c:
            resp = c.post('/api/hasheddoc/', data=json.dumps({'data': 'd1'}),
                          headers=self.bearer(self.raw))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(g.user, self.normal)
            self.assertEqual(HashedDoc.get(data='d1').user, self.normal)

    def test_owner_restriction_via_token(self):
        doc = HashedDoc.create(user=self.normal, data='orig')
        _, admin_raw = HashedToken.create_token(user=self.admin)
        with self.flask_app.test_client() as c:
            resp = c.put('/api/hasheddoc/%s/' % doc.id,
                         data=json.dumps({'data': 'hax'}),
                         headers=self.bearer(admin_raw))
            self.assertEqual(resp.status_code, 403)

            resp = c.put('/api/hasheddoc/%s/' % doc.id,
                         data=json.dumps({'data': 'edit'}),
                         headers=self.bearer(self.raw))
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(HashedDoc.get(id=doc.id).data, 'edit')
