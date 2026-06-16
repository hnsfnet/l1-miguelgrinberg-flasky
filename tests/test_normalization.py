import re
import unittest
from app import create_app, db
from app.models import User, Role


class NormalizationModelTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_normalize_email(self):
        self.assertEqual(User.normalize_email('John@Example.COM'),
                         'john@example.com')
        self.assertEqual(User.normalize_email('  user@test.com  '),
                         'user@test.com')
        self.assertEqual(User.normalize_email(' A@B.C '), 'a@b.c')
        self.assertIsNone(User.normalize_email(None))

    def test_normalize_username(self):
        self.assertEqual(User.normalize_username('John'), 'john')
        self.assertEqual(User.normalize_username('  john  '), 'john')
        self.assertEqual(User.normalize_username(' John '), 'john')
        self.assertIsNone(User.normalize_username(None))

    def test_model_auto_normalizes_email(self):
        u = User(email='John@Example.COM', username='john', password='cat')
        self.assertEqual(u.email, 'john@example.com')

    def test_model_auto_normalizes_username(self):
        u = User(email='john@example.com', username='  John  ', password='cat')
        self.assertEqual(u.username, 'john')

    def test_model_email_change_normalizes(self):
        u = User(email='john@example.com', username='john', password='cat')
        db.session.add(u)
        db.session.commit()
        token = u.generate_email_change_token('Susan@Example.ORG')
        self.assertTrue(u.change_email(token))
        self.assertEqual(u.email, 'susan@example.org')

    def test_model_email_change_duplicate_case_insensitive(self):
        u1 = User(email='john@example.com', username='john', password='cat')
        u2 = User(email='susan@example.org', username='susan', password='dog')
        db.session.add_all([u1, u2])
        db.session.commit()
        token = u2.generate_email_change_token('JOHN@EXAMPLE.COM')
        self.assertFalse(u2.change_email(token))
        self.assertEqual(u2.email, 'susan@example.org')


class NormalizationRegistrationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_register_stores_normalized_email(self):
        response = self.client.post('/auth/register', data={
            'email': 'John@Example.COM',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        self.assertEqual(response.status_code, 302)
        user = User.query.filter_by(username='john').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'john@example.com')

    def test_register_stores_normalized_username(self):
        response = self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'John',
            'password': 'cat',
            'password2': 'cat'
        })
        self.assertEqual(response.status_code, 302)
        user = User.query.filter_by(email='john@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'john')

    def test_register_duplicate_email_case_insensitive(self):
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        response = self.client.post('/auth/register', data={
            'email': 'JOHN@EXAMPLE.COM',
            'username': 'jane',
            'password': 'cat',
            'password2': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Email already registered',
                      response.get_data(as_text=True))

    def test_register_duplicate_username_case_insensitive(self):
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        response = self.client.post('/auth/register', data={
            'email': 'jane@example.com',
            'username': 'John',
            'password': 'cat',
            'password2': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Username already in use',
                      response.get_data(as_text=True))


class NormalizationLoginTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)
        # register a user
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_login_case_insensitive_email(self):
        response = self.client.post('/auth/login', data={
            'email': 'JOHN@EXAMPLE.COM',
            'password': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Hello', response.get_data(as_text=True))

    def test_login_with_spaces_in_email(self):
        response = self.client.post('/auth/login', data={
            'email': '  john@example.com  ',
            'password': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Hello', response.get_data(as_text=True))


class NormalizationEmailChangeTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)
        # register and login
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        self.client.post('/auth/login', data={
            'email': 'john@example.com',
            'password': 'cat'
        })

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_change_email_duplicate_case_insensitive(self):
        # register another user
        u2 = User(email='susan@example.org', username='susan', password='dog')
        db.session.add(u2)
        db.session.commit()
        # try to change to existing email with different case
        response = self.client.post('/auth/change_email', data={
            'email': 'SUSAN@EXAMPLE.ORG',
            'password': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Email already registered',
                      response.get_data(as_text=True))


class NormalizationAdminEditTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)
        # create an admin user
        admin_role = Role.query.filter_by(name='Administrator').first()
        self.admin = User(email='admin@example.com', username='admin',
                          password='admin', role=admin_role, confirmed=True)
        self.target = User(email='john@example.com', username='john',
                           password='cat', confirmed=True)
        db.session.add_all([self.admin, self.target])
        db.session.commit()
        # login as admin
        self.client.post('/auth/login', data={
            'email': 'admin@example.com',
            'password': 'admin'
        })

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_admin_edit_same_email_different_case_no_error(self):
        response = self.client.post(
            '/edit-profile/{}'.format(self.target.id), data={
                'email': 'JOHN@EXAMPLE.COM',
                'username': 'john',
                'confirmed': True,
                'role': self.target.role_id,
                'name': '',
                'location': '',
                'about_me': ''
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Email already registered',
                         response.get_data(as_text=True))

    def test_admin_edit_same_username_different_case_no_error(self):
        response = self.client.post(
            '/edit-profile/{}'.format(self.target.id), data={
                'email': 'john@example.com',
                'username': 'JOHN',
                'confirmed': True,
                'role': self.target.role_id,
                'name': '',
                'location': '',
                'about_me': ''
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Username already in use',
                         response.get_data(as_text=True))

    def test_admin_edit_duplicate_email_different_user(self):
        response = self.client.post(
            '/edit-profile/{}'.format(self.target.id), data={
                'email': 'Admin@Example.COM',
                'username': 'john',
                'confirmed': True,
                'role': self.target.role_id,
                'name': '',
                'location': '',
                'about_me': ''
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Email already registered',
                      response.get_data(as_text=True))

    def test_admin_edit_duplicate_username_different_user(self):
        response = self.client.post(
            '/edit-profile/{}'.format(self.target.id), data={
                'email': 'john@example.com',
                'username': 'Admin',
                'confirmed': True,
                'role': self.target.role_id,
                'name': '',
                'location': '',
                'about_me': ''
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Username already in use',
                      response.get_data(as_text=True))
