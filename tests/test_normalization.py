import re
import unittest
from app import create_app, db
from app.models import User, Role


class NormalizationModelTestCase(unittest.TestCase):
    """Test that the User model normalizes email and username on assignment."""

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

    def test_email_stripped_and_lowered_on_create(self):
        u = User(email='  John@Example.COM  ', username='john', password='cat')
        self.assertEqual(u.email, 'john@example.com')

    def test_username_stripped_and_lowered_on_create(self):
        u = User(email='a@b.com', username='  John  ', password='cat')
        self.assertEqual(u.username, 'john')

    def test_email_normalized_on_assignment(self):
        u = User(email='a@b.com', username='john', password='cat')
        db.session.add(u)
        db.session.commit()
        u.email = '  Susan@Example.ORG  '
        self.assertEqual(u.email, 'susan@example.org')

    def test_username_normalized_on_assignment(self):
        u = User(email='a@b.com', username='john', password='cat')
        db.session.add(u)
        db.session.commit()
        u.username = '  SUSAN  '
        self.assertEqual(u.username, 'susan')

    def test_none_email_stays_none(self):
        u = User(password='cat')
        u.email = None
        self.assertIsNone(u.email)

    def test_none_username_stays_none(self):
        u = User(password='cat')
        u.username = None
        self.assertIsNone(u.username)

    def test_duplicate_email_case_insensitive(self):
        """Two users with same email (different case) should violate unique."""
        u1 = User(email='john@example.com', username='john', password='cat')
        db.session.add(u1)
        db.session.commit()
        # Both normalize to the same email — DB unique constraint should catch
        from sqlalchemy.exc import IntegrityError
        u2 = User(email='JOHN@EXAMPLE.COM', username='other', password='dog')
        db.session.add(u2)
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_duplicate_username_case_insensitive(self):
        """Two users with same username (different case) should violate unique."""
        u1 = User(email='a@b.com', username='john', password='cat')
        db.session.add(u1)
        db.session.commit()
        from sqlalchemy.exc import IntegrityError
        u2 = User(email='c@d.com', username='JOHN', password='dog')
        db.session.add(u2)
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()


class NormalizationRegistrationTestCase(unittest.TestCase):
    """Test that registration normalizes inputs and rejects duplicates."""

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

    def test_register_normalizes_email(self):
        response = self.client.post('/auth/register', data={
            'email': '  John@Example.COM  ',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        self.assertEqual(response.status_code, 302)
        user = User.query.first()
        self.assertEqual(user.email, 'john@example.com')

    def test_register_normalizes_username(self):
        response = self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': '  John  ',
            'password': 'cat',
            'password2': 'cat'
        })
        self.assertEqual(response.status_code, 302)
        user = User.query.first()
        self.assertEqual(user.username, 'john')

    def test_register_rejects_duplicate_email_different_case(self):
        # Register first user
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        # Try to register with same email in different case
        response = self.client.post('/auth/register', data={
            'email': 'JOHN@EXAMPLE.COM',
            'username': 'other',
            'password': 'dog',
            'password2': 'dog'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Email already registered',
                       response.get_data(as_text=True))

    def test_register_rejects_duplicate_username_different_case(self):
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        response = self.client.post('/auth/register', data={
            'email': 'other@example.com',
            'username': 'JOHN',
            'password': 'dog',
            'password2': 'dog'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Username already in use',
                       response.get_data(as_text=True))

    def test_register_rejects_duplicate_email_with_whitespace(self):
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        response = self.client.post('/auth/register', data={
            'email': '  john@example.com  ',
            'username': 'other',
            'password': 'dog',
            'password2': 'dog'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Email already registered',
                       response.get_data(as_text=True))

    def test_register_rejects_duplicate_username_with_whitespace(self):
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        response = self.client.post('/auth/register', data={
            'email': 'other@example.com',
            'username': '  john  ',
            'password': 'dog',
            'password2': 'dog'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Username already in use',
                       response.get_data(as_text=True))


class NormalizationLoginTestCase(unittest.TestCase):
    """Test that login works regardless of email case/whitespace."""

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)
        # Register and confirm a user
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        user = User.query.filter_by(email='john@example.com').first()
        token = user.generate_confirmation_token()
        user.confirm(token)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_login_with_exact_email(self):
        response = self.client.post('/auth/login', data={
            'email': 'john@example.com',
            'password': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(re.search('Hello,\s+john',
                                  response.get_data(as_text=True)))

    def test_login_with_uppercase_email(self):
        response = self.client.post('/auth/login', data={
            'email': 'JOHN@EXAMPLE.COM',
            'password': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(re.search('Hello,\s+john',
                                  response.get_data(as_text=True)))

    def test_login_with_mixed_case_email(self):
        response = self.client.post('/auth/login', data={
            'email': 'John@Example.Com',
            'password': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(re.search('Hello,\s+john',
                                  response.get_data(as_text=True)))

    def test_login_with_whitespace_email(self):
        response = self.client.post('/auth/login', data={
            'email': '  john@example.com  ',
            'password': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(re.search('Hello,\s+john',
                                  response.get_data(as_text=True)))


class NormalizationChangeEmailTestCase(unittest.TestCase):
    """Test email change with normalization."""

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)
        # Register, confirm, and login a user
        self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        user = User.query.filter_by(email='john@example.com').first()
        token = user.generate_confirmation_token()
        user.confirm(token)
        db.session.commit()
        self.client.post('/auth/login', data={
            'email': 'john@example.com',
            'password': 'cat'
        })

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_change_email_normalizes(self):
        response = self.client.post('/auth/change_email', data={
            'email': '  NewEmail@Example.ORG  ',
            'password': 'cat'
        })
        self.assertEqual(response.status_code, 302)
        # The token should contain the normalized email
        user = User.query.filter_by(email='john@example.com').first()
        self.assertIsNotNone(user)
        # Test via the model directly
        token = user.generate_email_change_token('newemail@example.org')
        self.assertTrue(user.change_email(token))
        self.assertEqual(user.email, 'newemail@example.org')

    def test_change_email_rejects_duplicate_case_insensitive(self):
        # Create another user with a specific email
        u2 = User(email='susan@example.org', username='susan', password='dog')
        db.session.add(u2)
        db.session.commit()
        # Try to change john's email to susan's email (different case)
        user = User.query.filter_by(email='john@example.com').first()
        token = user.generate_email_change_token('SUSAN@EXAMPLE.ORG')
        self.assertFalse(user.change_email(token))
        self.assertEqual(user.email, 'john@example.com')


class NormalizationAdminEditTestCase(unittest.TestCase):
    """Test admin edit profile with normalization."""

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)
        # Create an admin user
        admin_role = Role.query.filter_by(name='Administrator').first()
        self.admin = User(email='admin@example.com', username='admin',
                          password='admin', role=admin_role, confirmed=True)
        db.session.add(self.admin)
        # Create a regular user
        self.user = User(email='john@example.com', username='john',
                         password='cat', confirmed=True)
        db.session.add(self.user)
        db.session.commit()
        # Login as admin
        self.client.post('/auth/login', data={
            'email': 'admin@example.com',
            'password': 'admin'
        })

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_admin_edit_normalizes_email(self):
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': '  NewEmail@Example.ORG  ',
                'username': 'john',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.user)
        self.assertEqual(self.user.email, 'newemail@example.org')

    def test_admin_edit_normalizes_username(self):
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': 'john@example.com',
                'username': '  NewName  ',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.user)
        self.assertEqual(self.user.username, 'newname')

    def test_admin_edit_same_email_different_case_no_error(self):
        """Changing user's own email to different case should not fail."""
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': 'JOHN@EXAMPLE.COM',
                'username': 'john',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.user)
        self.assertEqual(self.user.email, 'john@example.com')

    def test_admin_edit_same_username_different_case_no_error(self):
        """Changing user's own username to different case should not fail."""
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': 'john@example.com',
                'username': 'JOHN',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.user)
        self.assertEqual(self.user.username, 'john')

    def test_admin_edit_same_email_with_whitespace_no_error(self):
        """Changing user's own email with added whitespace should not fail."""
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': '  john@example.com  ',
                'username': 'john',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.user)
        self.assertEqual(self.user.email, 'john@example.com')

    def test_admin_edit_same_username_with_whitespace_no_error(self):
        """Changing user's own username with whitespace should not fail."""
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': 'john@example.com',
                'username': '  john  ',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.user)
        self.assertEqual(self.user.username, 'john')

    def test_admin_edit_rejects_duplicate_email(self):
        """Admin should not be able to set user's email to another user's."""
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': 'admin@example.com',
                'username': 'john',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Email already registered',
                       response.get_data(as_text=True))

    def test_admin_edit_rejects_duplicate_username(self):
        """Admin should not be able to set user's username to another user's."""
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': 'john@example.com',
                'username': 'admin',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Username already in use',
                       response.get_data(as_text=True))

    def test_admin_edit_rejects_duplicate_email_different_case(self):
        """Duplicate email detection should be case-insensitive."""
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': 'ADMIN@EXAMPLE.COM',
                'username': 'john',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Email already registered',
                       response.get_data(as_text=True))

    def test_admin_edit_rejects_duplicate_username_different_case(self):
        """Duplicate username detection should be case-insensitive."""
        response = self.client.post(
            '/edit-profile/{}'.format(self.user.id), data={
                'email': 'john@example.com',
                'username': 'ADMIN',
                'confirmed': True,
                'role': self.user.role_id,
                'name': 'John',
                'location': '',
                'about_me': ''
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Username already in use',
                       response.get_data(as_text=True))


class NormalizationURLLookupTestCase(unittest.TestCase):
    """Test that URL-based username lookups are case-insensitive."""

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)
        self.user = User(email='john@example.com', username='john',
                         password='cat', confirmed=True)
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_profile_page_case_insensitive(self):
        response = self.client.get('/user/JOHN')
        self.assertEqual(response.status_code, 200)

    def test_profile_page_with_whitespace(self):
        response = self.client.get('/user/%20john%20')
        # URL-encoded spaces should be normalized
        self.assertEqual(response.status_code, 200)
