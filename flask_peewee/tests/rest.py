from __future__ import with_statement

try:
    import simplejson as json
except ImportError:
    import json

import base64
import datetime
import unittest

from flask import g

from flask_peewee.rest import RestAPI, RestResource, Authentication, UserAuthentication
from flask_peewee.tests.base import FlaskPeeweeTestCase
from flask_peewee.tests.test_app import User, Message, Note, TestModel, APIKey
from flask_peewee.utils import get_next, make_password, check_password


class RestApiTestCase(FlaskPeeweeTestCase):
    def setUp(self):
        super(RestApiTestCase, self).setUp()
        TestModel.drop_table(True)
        APIKey.drop_table(True)
        APIKey.create_table()
        TestModel.create_table()
    
    def response_json(self, response):
        return json.loads(response.data)
    
    def auth_headers(self, username, password):
        return {'Authorization': 'Basic %s' % base64.b64encode('%s:%s' % (username, password))}
            
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
        self.assertAPIMeta(resp_json, {
            'model': 'note',
            'previous': '',
            'next': '/api/note/?ordering=id&page=2',
            'page': 1,
        })
        
        # verify response objects are paginated properly
        self.assertAPINotes(resp_json, notes[:20])
        
        # do a list of first 10 items
        resp = self.app.get('/api/note/?ordering=id&limit=10')
        resp_json = self.response_json(resp)
        
        self.assertAPIMeta(resp_json, {
            'model': 'note',
            'previous': '',
            'next': '/api/note/?ordering=id&limit=10&page=2',
            'page': 1,
        })
        
        # verify response objects are paginated properly
        self.assertAPINotes(resp_json, notes[:10])
        
        # grab the second page
        resp = self.app.get(resp_json['meta']['next'])
        resp_json = self.response_json(resp)
        
        self.assertAPIMeta(resp_json, {
            'model': 'note',
            'previous': '/api/note/?ordering=id&limit=10&page=1',
            'next': '/api/note/?ordering=id&limit=10&page=3',
            'page': 2,
        })
        
        # verify response objects are paginated properly
        self.assertAPINotes(resp_json, notes[10:20])
        
        # grab the last page
        resp = self.app.get(resp_json['meta']['next'])
        resp_json = self.response_json(resp)
        
        self.assertAPIMeta(resp_json, {
            'model': 'note',
            'previous': '/api/note/?ordering=id&limit=10&page=2',
            'next': '',
            'page': 3,
        })
        
        # verify response objects are paginated properly
        self.assertAPINotes(resp_json, notes[20:])
    
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
        })
        self.assertAPINotes(resp_json, self.normal.note_set.order_by('id'))
        
        # do a filter following a join
        resp = self.app.get('/api/note/?user__username=admin&ordering=id')
        resp_json = self.response_json(resp)
        
        self.assertAPIMeta(resp_json, {
            'model': 'note',
            'previous': '',
            'next': '',
            'page': 1,
        })
        self.assertAPINotes(resp_json, self.admin.note_set.order_by('id'))
        
        # filter multiple fields
        notes = list(self.admin.note_set.order_by('id'))
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
        })
        self.assertAPINotes(resp_json, Note.filter(user__in=[self.admin, self.inactive]).order_by('id'))
    
    def test_filter_with_pagination(self):
        users, notes = self.get_users_and_notes()
        notes = list(self.admin.note_set.order_by('id'))
        
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
        self.assertAPIMeta(resp_json, {'model': 'note', 'next': '', 'page': 1, 'previous': ''})
        
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
        self.assertAPIMeta(resp_json, {'model': 'message', 'next': '', 'page': 1, 'previous': ''})
        
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
        self.assertAPIMeta(resp_json, {'model': 'user', 'next': '', 'page': 1, 'previous': ''})
        
        self.create_users()
        
        resp = self.app.get('/api/user/?ordering=id')
        resp_json = self.response_json(resp)
        
        self.assertAPIUsers(resp_json, [
            self.admin,
            self.normal,
        ])
    
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
        
        user_data = {'username': 'test', 'password': new_pass}
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
        
        user_data = {'username': 'test', 'password': new_pass}
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
            self.assertAPIMeta(resp_json, {'model': 'testmodel', 'next': '', 'page': 1, 'previous': ''})
    
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
