import json

from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import (
    db, AModel, BModel, BDetails, CModel,
    DModel, EModel, FModel, JModel, Message,
    Note, User,
)


class RestApiTestCase(FlaskPeeweeTestCase):

    def conv_date(self, dt):
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def assertAPIResponse(self, resp_json, body):
        self.assertEqual(body, resp_json['objects'])

    def assertAPIMeta(self, resp_json, meta):
        self.assertEqual(meta, resp_json['meta'])

    def assertAPIUser(self, json_data, user):
        self.assertEqual(json_data, {
            'username': user.username,
            'active': user.active,
            'join_date': self.conv_date(user.join_date),
            'admin': user.admin,
            'id': user.id,
        })

    def assertAPIJModels(self, json_data, jmodels):
        for json_item, jmodel in zip(json_data['objects'], jmodels):
            self.assertAPIJModel(json_item, jmodel)

    def assertAPIJModel(self, json_data, jmodel):
        self.assertEqual(json_data, {
            'id': jmodel.id,
            'j_field': jmodel.j_field,
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


class RestApiResourceTestCase(RestApiTestCase):
    def setUp(self):
        super().setUp()
        db.create_tables([
            AModel,
            BModel,
            BDetails,
            CModel,
            DModel,
            EModel,
            FModel,
            JModel,
        ])
        JModel.delete().execute()
        FModel.delete().execute()
        EModel.delete().execute()
        DModel.delete().execute()
        CModel.delete().execute()
        BModel.delete().execute()
        BDetails.delete().execute()
        AModel.delete().execute()

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
        self.j1 = JModel.create(j_field={'foo': {'star': 'far'}, 'bar': 'car', 'n': None})

    def test_resources_list_detail(self):
        self.create_test_models()

        # amodel
        resp = self.app.get('/api/amodel?ordering=id')
        self.assertEqual(resp.get_json()['objects'], [
            {'id': self.a1.id, 'a_field': 'a1'},
            {'id': self.a2.id, 'a_field': 'a2'},
        ])

        resp = self.app.get('/api/amodel/%s' % self.a2.id)
        self.assertEqual(resp.get_json(), {
            'id': self.a2.id,
            'a_field': 'a2',
        })

        # bmodel
        resp = self.app.get('/api/bmodel?ordering=id')
        self.assertEqual(resp.get_json()['objects'], [
            {'id': self.b1.id, 'b_field': 'b1', 'a': {'id': self.a1.id, 'a_field': 'a1'}},
            {'id': self.b2.id, 'b_field': 'b2', 'a': {'id': self.a2.id, 'a_field': 'a2'}},
        ])

        resp = self.app.get('/api/bmodel/%s' % self.b2.id)
        self.assertEqual(resp.get_json(), {
            'id': self.b2.id,
            'b_field': 'b2',
            'a': {'id': self.a2.id, 'a_field': 'a2'},
        })

        # cmodel
        resp = self.app.get('/api/cmodel?ordering=id')
        self.assertEqual(resp.get_json()['objects'], [
            {'id': self.c1.id, 'c_field': 'c1', 'b': {'id': self.b1.id, 'b_field': 'b1', 'a': {'id': self.a1.id, 'a_field': 'a1'}}},  # NOQA
            {'id': self.c2.id, 'c_field': 'c2', 'b': {'id': self.b2.id, 'b_field': 'b2', 'a': {'id': self.a2.id, 'a_field': 'a2'}}},  # NOQA
        ])

        resp = self.app.get('/api/cmodel/%s' % self.c2.id)
        self.assertEqual(resp.get_json(), {
            'id': self.c2.id,
            'c_field': 'c2',
            'b': {'id': self.b2.id, 'b_field': 'b2', 'a': {'id': self.a2.id, 'a_field': 'a2'}},
        })

        # fmodel
        resp = self.app.get('/api/fmodel?ordering=id')
        self.assertEqual(resp.get_json()['objects'], [
            {'id': self.f1.id, 'f_field': 'f1', 'e': {'id': self.e1.id, 'e_field': 'e1'}},
            {'id': self.f2.id, 'f_field': 'f2', 'e': None},
        ])

        resp = self.app.get('/api/fmodel/%s' % self.f1.id)
        self.assertEqual(resp.get_json(), {
            'id': self.f1.id,
            'f_field': 'f1',
            'e': {'id': self.e1.id, 'e_field': 'e1'},
        })

        resp = self.app.get('/api/fmodel/%s' % self.f2.id)
        self.assertEqual(resp.get_json(), {
            'id': self.f2.id,
            'f_field': 'f2',
            'e': None,
        })

        resp = self.app.get('/api/jmodel/%s' % self.j1.id)
        self.assertEqual(resp.get_json(), {
            'id': self.j1.id,
            'j_field': {'foo': {'star': 'far'}, 'bar': 'car', 'n': None},
        })

    def test_resources_count(self):
        self.create_test_models()

        # amodel
        resp = self.app.get('/api/amodel/_count')
        self.assertEqual(resp.get_json()['count'], 2)

        resp = self.app.get('/api/amodel')
        self.assertEqual(resp.get_json()['meta']['count'], 2)

        # fmodel
        resp = self.app.get('/api/fmodel/_count')
        self.assertEqual(resp.status_code, 404)

        resp = self.app.get('/api/fmodel')
        self.assertEqual(resp.get_json()['meta']['count'], None)

    def test_resources_exportable(self):
        self.create_test_models()

        # amodel
        resp = self.app.get('/api/amodel/_exportable')
        self.assertEqual(resp.get_json(), {'fields': [{'field': 'a_field', 'name': 'A'}]})

        # amodel
        resp = self.app.get('/api/amodel?format=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_data(), b'A\r\na1\r\na2\r\n')

    def test_resources_registry(self):
        # amodel
        resp = self.app.get('/api/amodel/_registry')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {
            'name': 'amodel',
            'fields': [
                {'name': 'id', 'type': 'AutoField'},
                {'name': 'a_field', 'type': 'CharField'},
            ],
            'groups': [
                {'name': 'id', 'type': 'AutoField'},
                {'name': 'a_field', 'type': 'CharField'}
            ],
        })

        # bmodel
        resp = self.app.get('/api/bmodel/_registry')
        self.assertEqual(resp.status_code, 403)

    def test_reverse_resources(self):
        self.create_test_models()
        CModel.delete().execute()

        # Test reverse resource serialization
        resp = self.app.get('/api/amodelv2')
        self.assertEqual(resp.get_json(), [
            {'a_field': 'a1', 'bmodel_set': [{'a': self.a1.id, 'b_field': 'b1', 'c': None}], 'id': self.a1.id},
            {'a_field': 'a2', 'bmodel_set': [{'a': self.a2.id, 'b_field': 'b2', 'c': None}], 'id': self.a2.id},
        ])

        # Test filter on reverse resources
        resp = self.app.get('/api/amodelv2?bmodel__b_field=b2')
        self.assertEqual(resp.get_json(), [
            {'a_field': 'a2', 'bmodel_set': [{'a': self.a2.id, 'b_field': 'b2', 'c': None}], 'id': self.a2.id},
        ])

        # Test unique reverse resources
        self.c2 = CModel.create(c_field='c2', b=self.b2)
        resp = self.app.get('/api/bmodelv2?b_field=b2')
        self.assertEqual(resp.get_json(), [
            {'a': self.a2.id, 'b_field': 'b2', 'c': {"c_field": "c2", "b": self.b2.id}},
        ])

        # Test empty reverse resources
        AModel.create(a_field='a3')
        resp = self.app.get('/api/amodelv2')
        resp_json = resp.get_json()
        self.assertEqual(resp_json[2]["bmodel_set"], [])

        # Test many to one reverse resources
        BModel.create(b_field='b11', a=self.a1)
        resp = self.app.get('/api/amodelv2')
        resp_json = resp.get_json()
        self.assertEqual(len(resp_json), 3)
        self.assertEqual(len(resp_json[0]["bmodel_set"]), 2)

    def post_to(self, url, data):
        return self.app.post(url, data=json.dumps(data))

    def delete_to(self, url):
        return self.app.delete(url)

    def test_resources_create(self):
        # a model
        resp = self.post_to('/api/amodel', {'a_field': 'ax'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(AModel.select().count(), 1)
        a_obj = AModel.get(a_field='ax')
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': a_obj.id,
            'a_field': 'ax',
        })

        # b model
        resp = self.post_to('/api/bmodel', {'b_field': 'by', 'a': {'a_field': 'ay'}})
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
        resp = self.post_to('/api/cmodel', {'c_field': 'cz', 'b': {'b_field': 'bz', 'a': {'a_field': 'az'}}})  # NOQA
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
        resp = self.post_to('/api/fmodel', {'f_field': 'fy', 'e': {'e_field': 'ey'}})
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

        resp = self.post_to('/api/fmodel', {'f_field': 'fz'})
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

    def test_resources_edit(self):
        self.create_test_models()

        # a
        resp = self.post_to('/api/amodel/%s' % self.a2.id, {'a_field': 'a2-xxx'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(AModel.select().count(), 2)
        a_obj = AModel.get(id=self.a2.id)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {
            'id': self.a2.id,
            'a_field': 'a2-xxx',
        })

        # b
        resp = self.post_to('/api/bmodel/%s' % self.b2.id, {'b_field': 'b2-yyy', 'a': {'a_field': 'a2-yyy'}})  # NOQA
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
        resp = self.post_to('/api/cmodel/%s' % self.c2.id, {'c_field': 'c2-zzz', 'b': {'b_field': 'b2-zzz', 'a': {'a_field': 'a2-zzz'}}})  # NOQA
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
        resp = self.post_to('/api/fmodel/%s' % self.f1.id, {'f_field': 'f1-yyy', 'e': {'e_field': 'e1-yyy'}})  # NOQA
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

        resp = self.post_to('/api/fmodel/%s' % self.f2.id, {'f_field': 'f2-yyy'})
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
        resp = self.post_to('/api/bmodel/%s' % self.b2.id, {'b_field': 'b2-yyy'})
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
        resp = self.post_to('/api/fmodel/%s' % self.f1.id, {'f_field': 'f1-zzz'})
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

    def test_resource_edit_by_fk(self):
        self.create_test_models()

        # b model
        resp = self.post_to('/api/bmodel/%s' % self.b2.id, {'a': self.a1.id})
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
        resp = self.post_to('/api/fmodel/%s' % self.f2.id, {'e': self.e2.id})
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

        resp = self.delete_to('/api/cmodel/%s' % self.c2.id)
        self.assertEqual(resp.get_json(), {'deleted': 1})

        self.assertEqual(CModel.select().count(), 1)
        self.assertEqual(BModel.select().count(), 2)
        self.assertEqual(AModel.select().count(), 2)

        resp = self.delete_to('/api/amodel/%s' % self.a1.id)
        self.assertEqual(resp.get_json(), {'deleted': 1})

        self.assertEqual(CModel.select().count(), 0)
        self.assertEqual(BModel.select().count(), 1)
        self.assertEqual(AModel.select().count(), 1)

        resp = self.delete_to('/api/emodel/%s' % self.e1.id)
        self.assertEqual(json.loads(resp.data.decode('utf8')), {'deleted': 1})

        self.assertEqual(EModel.select().count(), 1)
        self.assertEqual(FModel.select().count(), 2)

        f_obj = FModel.get(id=self.f1.id)
        self.assertEqual(f_obj.e, None)

    def test_json_filtering(self):
        # test that filtering on JSON fields works
        resp = self.app.get('/api/jmodel?j_field.bar=car')
        self.assertAPIJModels(
            resp.get_json(),
            JModel.select().where(JModel.j_field['bar'] == 'car').order_by(JModel.id))

    def test_json_value(self):
        self.create_test_models()
        # test wrong pk
        resp = self.app.get('/api/jmodel/9000/j_field/new')
        self.assertEqual(resp.status_code, 404)

        # test wrong field name
        resp = self.app.get('/api/jmodel/%s/no_field/new' % self.j1.id)
        self.assertEqual(resp.status_code, 404)

        url = '/api/jmodel/%s' % self.j1.id

        resp = self.app.get(url + '/j_field/foo')
        self.assertEqual(resp.status_code, 200)
        assert resp.get_json() == {'star': 'far'}

        resp = self.app.get(url + '/j_field/foo/star')
        self.assertEqual(resp.status_code, 200)
        assert resp.get_json() == 'far'

        resp = self.app.get(url + '/j_field/foo/tzar')
        self.assertEqual(resp.status_code, 404)

        resp = self.app.get(url + '/j_field/n')
        self.assertEqual(resp.status_code, 200)
        assert resp.get_json() == None

        resp = self.app.get(url + '/j_field/foo/star/car')
        self.assertEqual(resp.status_code, 404)

        resp = self.app.get(url + '/j_field/foo/star/car')
        self.assertEqual(resp.status_code, 404)

        resp = self.app.get(url + '/j_field/foo/star')
        self.assertEqual(resp.status_code, 200)

    def test_json_edit(self):
        self.create_test_models()
        # test wrong pk
        resp = self.app.put('/api/jmodel/9000/j_field/new', json='value')
        self.assertEqual(resp.status_code, 404)

        # test wrong field name
        resp = self.app.put('/api/jmodel/%s/no_field/new' % self.j1.id, json='value')
        self.assertEqual(resp.status_code, 404)

        url = '/api/jmodel/%s' % self.j1.id
        resp = self.app.put(url + '/j_field/new', json='value')
        self.assertEqual(resp.status_code, 200)
        j1 = JModel.get(JModel.id == self.j1.id)
        assert resp.get_json() == 'value'
        assert j1.j_field == {'foo': {'star': 'far'}, 'bar': 'car', 'n': None, 'new': 'value'}

        resp = self.app.put(url + '/j_field/foo', json={'planet': 'mars'})
        self.assertEqual(resp.status_code, 200)
        j1 = JModel.get(JModel.id == self.j1.id)
        assert resp.get_json() == {'planet': 'mars'}
        assert j1.j_field == {'foo': {'planet': 'mars'}, 'bar': 'car', 'n': None, 'new': 'value'}

        # test -p ness
        resp = self.app.put(url + '/j_field/fast/cars', json={'toycar': 1})
        self.assertEqual(resp.status_code, 200)
        j1 = JModel.get(JModel.id == self.j1.id)
        assert resp.get_json() == {'toycar': 1}
        assert j1.j_field['fast'] == {'cars': {'toycar': 1}}

    def test_json_delete(self):
        self.create_test_models()
        # test wrong pk
        resp = self.app.delete('/api/jmodel/9000/j_field/foo')
        self.assertEqual(resp.status_code, 404)

        # test wrong field name
        resp = self.app.delete('/api/jmodel/%s/no_field/foo' % self.j1.id)
        self.assertEqual(resp.status_code, 404)

        url = '/api/jmodel/%s' % self.j1.id
        resp = self.app.delete(url + '/j_field')
        self.assertEqual(resp.status_code, 404)

        resp = self.app.delete(url + '/j_field/foo/star/far/car')
        self.assertEqual(resp.status_code, 200)
        assert resp.get_json()['deleted'] is False
        j1 = JModel.get(JModel.id == self.j1.id)
        assert j1.j_field == self.j1.j_field

        resp = self.app.delete(url + '/j_field/foo/star')
        self.assertEqual(resp.status_code, 200)
        assert resp.get_json()['deleted'] is True

        resp = self.app.delete(url + '/j_field/foo')
        self.assertEqual(resp.status_code, 200)
        assert resp.get_json()['deleted'] is True

        j1 = JModel.get(JModel.id == self.j1.id)
        assert j1.j_field == {'bar': 'car', 'n': None}

        resp = self.app.delete(url + '/j_field/n')
        self.assertEqual(resp.status_code, 200)
        assert resp.get_json()['deleted'] is True

        j1 = JModel.get(JModel.id == self.j1.id)
        assert j1.j_field == {'bar': 'car'}

        resp = self.app.delete(url + '/j_field/foo')
        self.assertEqual(resp.status_code, 200)
        assert resp.get_json()['deleted'] is False

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
        resp = self.app.get('/api/note?ordering=id')

        # verify we have page and link to next page
        self.assertEqual(resp.get_json()['meta']['model'], 'note')
        self.assertEqual(resp.get_json()['meta']['previous'], '')
        self.assertEqual(resp.get_json()['meta']['page'], 1)
        self.assertTrue('page=2' in resp.get_json()['meta']['next'])

        # verify response objects are paginated properly
        self.assertAPINotes(resp.get_json(), notes[:20])

        # do a list of first 10 items
        resp = self.app.get('/api/note?ordering=id&limit=10')
        self.assertEqual(resp.get_json()['meta']['model'], 'note')
        self.assertEqual(resp.get_json()['meta']['previous'], '')
        self.assertEqual(resp.get_json()['meta']['page'], 1)
        self.assertTrue('page=2' in resp.get_json()['meta']['next'])

        # verify response objects are paginated properly
        self.assertAPINotes(resp.get_json(), notes[:10])

        # grab the second page
        resp = self.app.get(resp.get_json()['meta']['next'])
        self.assertEqual(resp.get_json()['meta']['model'], 'note')
        self.assertEqual(resp.get_json()['meta']['page'], 2)
        self.assertTrue('page=1' in resp.get_json()['meta']['previous'])
        self.assertTrue('page=3' in resp.get_json()['meta']['next'])

        # verify response objects are paginated properly
        self.assertAPINotes(resp.get_json(), notes[10:20])

        # grab the last page
        resp = self.app.get(resp.get_json()['meta']['next'])
        self.assertEqual(resp.get_json()['meta']['model'], 'note')
        self.assertEqual(resp.get_json()['meta']['next'], '')
        self.assertEqual(resp.get_json()['meta']['page'], 3)
        self.assertTrue('page=2' in resp.get_json()['meta']['previous'])

        # verify response objects are paginated properly
        self.assertAPINotes(resp.get_json(), notes[20:])

    def test_filtering(self):
        users, notes = self.get_users_and_notes()

        # do a simple filter on a related model
        resp = self.app.get('/api/note?user=%s&ordering=id' % self.normal.id)
        self.assertAPIMeta(resp.get_json(), {
            'count': 10,
            'model': 'note',
            'previous': '',
            'next': '',
            'page': 1,
        })
        self.assertAPINotes(resp.get_json(), self.normal.note_set.order_by(Note.id))

        # do a filter following a join
        resp = self.app.get('/api/note?user__username=admin&ordering=id')
        self.assertAPIMeta(resp.get_json(), {
            'count': 10,
            'model': 'note',
            'previous': '',
            'next': '',
            'page': 1,
        })
        self.assertAPINotes(resp.get_json(), self.admin.note_set.order_by(Note.id))

        # filter multiple fields
        notes = list(self.admin.note_set.order_by(Note.id))
        third_id = notes[3].id

        resp = self.app.get('/api/note?user__username=admin&id__lt=%s&ordering=id' % third_id)
        self.assertAPINotes(resp.get_json(), notes[:3])

        # do a filter using multiple values
        resp = self.app.get('/api/note?user__username=admin&user__username=inactive&ordering=id')
        self.assertAPIMeta(resp.get_json(), {
            'count': 20,
            'model': 'note',
            'previous': '',
            'next': '',
            'page': 1,
        })
        self.assertAPINotes(
            resp.get_json(),
            Note.filter(user__in=[self.admin, self.inactive]).order_by(Note.id))

        # do a filter with a negation
        resp = self.app.get('/api/note?-user__username=admin&ordering=id')
        self.assertAPINotes(resp.get_json(), Note.filter(user__in=[
            self.normal, self.inactive]).order_by(Note.id))

        # do a filter with an IN operator and multiple IDs
        # https://github.com/coleifer/flask-peewee/issues/112
        resp = self.app.get('/api/note?id__in=1&id__in=2&id__in=5')
        self.assertAPINotes(
            resp.get_json(),
            Note.filter(id__in=[1, 2, 5]).order_by(Note.id))

        # also test that the IN operator works with list of strings
        self.login(self.admin)
        resp = self.app.get('/api/user?username__in=admin,normal')
        self.assertAPIUsers(
            resp.get_json(),
            User.filter(username__in=['admin', 'normal']).order_by(User.id))

    def test_filter_with_pagination(self):
        users, notes = self.get_users_and_notes()
        notes = list(self.admin.note_set.order_by(Note.id))

        # do a simple filter on a related model
        resp = self.app.get('/api/note?user__username=admin&limit=4&ordering=id')
        self.assertAPINotes(resp.get_json(), notes[:4])

        next_url = resp.get_json()['meta']['next']
        resp = self.app.get(next_url)
        self.assertAPINotes(resp.get_json(), notes[4:8])

        next_url = resp.get_json()['meta']['next']
        resp = self.app.get(next_url)

        self.assertEqual(resp.get_json()['meta']['next'], '')
        self.assertAPINotes(resp.get_json(), notes[8:])

        prev_url = resp.get_json()['meta']['previous']
        resp = self.app.get(prev_url)
        self.assertAPINotes(resp.get_json(), notes[4:8])

        prev_url = resp.get_json()['meta']['previous']
        resp = self.app.get(prev_url)

        self.assertEqual(resp.get_json()['meta']['previous'], '')
        self.assertAPINotes(resp.get_json(), notes[:4])


class RestApiOwnerAuthTestCase(RestApiTestCase):
    def setUp(self):
        super().setUp()
        self.create_users()

    def create_messages(self):
        messages = [
            Message.create(user=self.admin, content='admin'),
            Message.create(user=self.normal, content='normal'),
        ]
        self.admin_message, self.normal_message = messages
        return messages

    def test_list_get(self):
        self.login(self.admin)
        resp = self.app.get('/api/message')
        self.assertEqual(resp.status_code, 200)
        self.assertAPIResponse(resp.get_json(), [])
        self.assertAPIMeta(resp.get_json(), {
            'count': 0,
            'model': 'message',
            'next': '',
            'page': 1,
            'previous': '',
        })

        self.create_messages()

        resp = self.app.get('/api/message?ordering=id')
        self.assertAPIMessages(resp.get_json(), [
            self.admin_message,
            self.normal_message,
        ])

    def test_detail_get(self):
        resp = self.app.get('/api/message/1')
        self.assertEqual(resp.status_code, 404)

        self.create_messages()
        self.login(self.normal)
        resp = self.app.get('/api/message/%s' % self.normal_message.id)
        self.assertAPIMessage(resp.get_json(), self.normal_message)

    def test_auth_create(self):
        message_data = {'content': 'test'}
        serialized = json.dumps(message_data)

        # this request is not authorized
        resp = self.app.post('/api/message', data=serialized)
        self.assertEqual(resp.status_code, 403)

        # authorized, user in database
        self.login(self.normal)
        resp = self.app.post('/api/message', data=serialized)
        self.assertEqual(resp.status_code, 200)

    def test_create(self):
        message_data = {'content': 'test'}
        serialized = json.dumps(message_data)

        # authorized as an admin
        self.login(self.normal)
        resp = self.app.post('/api/message', data=serialized)
        self.assertEqual(resp.status_code, 200)

        new_message = Message.get(content='test')
        self.assertEqual(new_message.user, self.normal)
        self.assertAPIMessage(resp.get_json(), new_message)

    def test_auth_edit(self):
        self.create_messages()

        message_data = {'content': 'edited'}
        serialized = json.dumps(message_data)

        url = '/api/message/%s' % self.normal_message.id

        # this request is not authorized
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 403)

        # authorized, user in database, but not owner
        self.login(self.inactive)
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 403)

        # authorized, user in database, is owner
        self.login(self.normal)
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 200)

        obj = Message.get(id=self.normal_message.id)
        self.assertEqual(obj.content, 'edited')

    def test_edit(self):
        self.create_messages()

        message_data = {'content': 'edited'}
        serialized = json.dumps(message_data)

        url = '/api/message/%s' % self.normal_message.id

        # authorized as normal
        self.login(self.normal)
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 200)

        message = Message.get(id=self.normal_message.id)
        self.assertEqual(message.content, 'edited')
        self.assertAPIMessage(resp.get_json(), message)

    def test_auth_delete(self):
        self.create_messages()

        url = '/api/message/%s' % self.normal_message.id

        # this request is not authorized
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 403)

        # authorized, user in database, not owner
        self.login(self.inactive)
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 403)

        # authorized, user in database, is owner
        self.login(self.normal)
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 200)

    def test_delete(self):
        self.create_messages()

        url = '/api/message/%s' % self.normal_message.id

        # authorized as an admin
        self.login(self.normal)
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Message.select().count(), 1)
        self.assertEqual(resp.get_json(), {'deleted': 1})


class RestApiAdminAuthTestCase(RestApiTestCase):
    def test_list_get(self):
        resp = self.app.get('/api/user')
        self.assertEqual(resp.status_code, 401)

        self.create_users()
        self.login(self.admin)
        resp = self.app.get('/api/user?ordering=id')
        self.assertAPIUsers(resp.get_json(), [
            self.admin,
            self.normal,
        ])

        resp = self.app.get('/api/user?admin=1')
        self.assertAPIUsers(resp.get_json(), [self.admin])

        resp = self.app.get('/api/user?admin=')
        self.assertAPIUsers(resp.get_json(), [self.normal])

    def test_detail_get(self):
        self.create_users()
        self.login(self.admin)
        resp = self.app.get('/api/user/100')
        self.assertEqual(resp.status_code, 404)

        resp = self.app.get('/api/user/%s' % self.normal.id)
        self.assertAPIUser(resp.get_json(), self.normal)

        resp = self.app.get('/api/user/%s' % self.inactive.id)
        self.assertEqual(resp.status_code, 404)

    def test_auth_create(self):
        self.create_users()

        user_data = {'username': 'test', 'password': 'test', 'email': ''}
        serialized = json.dumps(user_data)

        # this request is not authorized
        resp = self.app.post('/api/user', data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database, but not an administrator
        self.login(self.normal)
        resp = self.app.post('/api/user', data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized as an admin
        self.login(self.admin)
        resp = self.app.post('/api/user', data=serialized)
        self.assertEqual(resp.status_code, 200)

    def test_create(self):
        self.create_users()

        user_data = {'username': 'test', 'password': 'test', 'email': ''}
        serialized = json.dumps(user_data)

        # authorized as an admin
        self.login(self.admin)
        resp = self.app.post('/api/user', data=serialized)
        self.assertEqual(resp.status_code, 200)

        new_user = User.get(username='test')
        self.assertAPIUser(resp.get_json(), new_user)

    def test_auth_edit(self):
        self.create_users()

        user_data = {'username': 'edited'}
        serialized = json.dumps(user_data)

        url = '/api/user/%s' % self.normal.id

        # this request is not authorized
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database, but not an administrator
        self.login(self.normal)
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 401)

        # authorized as an admin
        self.login(self.admin)
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 200)

    def test_edit(self):
        self.create_users()

        user_data = {'username': 'edited'}
        serialized = json.dumps(user_data)

        url = '/api/user/%s' % self.normal.id

        # authorized as an admin
        self.login(self.admin)
        resp = self.app.put(url, data=serialized)
        self.assertEqual(resp.status_code, 200)

        user = User.get(id=self.normal.id)
        self.assertEqual(user.username, 'edited')
        self.assertAPIUser(resp.get_json(), user)

    def test_auth_delete(self):
        self.create_users()

        url = '/api/user/%s' % self.normal.id

        # this request is not authorized
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 401)

        # authorized, user in database, but not an administrator
        self.login(self.normal)
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 401)

        # authorized as an admin
        self.login(self.admin)
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 200)

    def test_delete(self):
        self.create_users()

        url = '/api/user/%s' % self.normal.id

        # authorized as an admin
        self.login(self.admin)
        resp = self.app.delete(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.select().count(), 2)
        self.assertEqual(resp.get_json(), {'deleted': 1})
