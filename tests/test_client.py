import re
import unittest
from app import create_app, db
from app.models import User, Role, Post, Comment, Permission


class FlaskClientTestCase(unittest.TestCase):
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

    def test_home_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue('Stranger' in response.get_data(as_text=True))

    def test_register_and_login(self):
        # register a new account
        response = self.client.post('/auth/register', data={
            'email': 'john@example.com',
            'username': 'john',
            'password': 'cat',
            'password2': 'cat'
        })
        self.assertEqual(response.status_code, 302)

        # login with the new account
        response = self.client.post('/auth/login', data={
            'email': 'john@example.com',
            'password': 'cat'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(re.search('Hello,\s+john!',
                                  response.get_data(as_text=True)))
        self.assertTrue(
            'You have not confirmed your account yet' in response.get_data(
                as_text=True))

        # send a confirmation token
        user = User.query.filter_by(email='john@example.com').first()
        token = user.generate_confirmation_token()
        response = self.client.get('/auth/confirm/{}'.format(token),
                                   follow_redirects=True)
        user.confirm(token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            'You have confirmed your account' in response.get_data(
                as_text=True))

        # log out
        response = self.client.get('/auth/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('You have been logged out' in response.get_data(
            as_text=True))

    def test_post_comment_pagination(self):
        self.app.config['FLASKY_COMMENTS_PER_PAGE'] = 2

        r_user = Role.query.filter_by(name='User').first()
        r_moderator = Role.query.filter_by(name='Moderator').first()
        u_regular = User(email='regular@example.com', username='regular',
                         password='cat', confirmed=True, role=r_user)
        u_moderator = User(email='moderator@example.com', username='moderator',
                           password='dog', confirmed=True, role=r_moderator)
        db.session.add_all([u_regular, u_moderator])
        db.session.commit()

        post = Post(body='body of the post', author=u_regular)
        db.session.add(post)
        db.session.commit()

        comments = [
            Comment(body='visible one', author=u_regular, post=post),
            Comment(body='visible two', author=u_regular, post=post),
            Comment(body='visible three', author=u_regular, post=post),
            Comment(body='disabled one', author=u_regular, post=post,
                    disabled=True),
            Comment(body='disabled two', author=u_regular, post=post,
                    disabled=True),
        ]
        db.session.add_all(comments)
        db.session.commit()

        self.assertEqual(post.visible_comment_count, 3)
        with self.app.test_request_context('/'):
            self.assertEqual(post.to_json()['comment_count'], 3)

        regular_query = post.comments.filter(
            (Comment.disabled == None) | (Comment.disabled == False))
        self.assertEqual(regular_query.count(), 3)

        pagination = regular_query.order_by(Comment.timestamp.asc()).paginate(
            page=1, per_page=self.app.config['FLASKY_COMMENTS_PER_PAGE'],
            error_out=False)
        self.assertEqual(pagination.total, 3)
        self.assertEqual([comment.body for comment in pagination.items],
                         ['visible one', 'visible two'])

        pagination2 = regular_query.order_by(Comment.timestamp.asc()).paginate(
            page=2, per_page=self.app.config['FLASKY_COMMENTS_PER_PAGE'],
            error_out=False)
        self.assertEqual([comment.body for comment in pagination2.items],
                         ['visible three'])

        moderator_query = post.comments.order_by(Comment.timestamp.asc())
        self.assertTrue(u_moderator.can(Permission.MODERATE))
        self.assertEqual(moderator_query.count(), 5)

        pagination3 = moderator_query.paginate(
            page=3, per_page=self.app.config['FLASKY_COMMENTS_PER_PAGE'],
            error_out=False)
        self.assertEqual([comment.body for comment in pagination3.items],
                         ['disabled two'])
