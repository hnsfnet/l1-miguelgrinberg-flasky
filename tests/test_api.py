import unittest
import json
import re
from base64 import b64encode
from app import create_app, db
from app.models import User, Role, Post, Comment


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def get_api_headers(self, username, password):
        return {
            'Authorization': 'Basic ' + b64encode(
                (username + ':' + password).encode('utf-8')).decode('utf-8'),
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def test_404(self):
        response = self.client.get(
            '/wrong/url',
            headers=self.get_api_headers('email', 'password'))
        self.assertEqual(response.status_code, 404)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['error'], 'not found')

    def test_no_auth(self):
        response = self.client.get('/api/v1/posts/',
                                   content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_bad_auth(self):
        # add a user
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u = User(email='john@example.com', password='cat', confirmed=True,
                 role=r)
        db.session.add(u)
        db.session.commit()

        # authenticate with bad password
        response = self.client.get(
            '/api/v1/posts/',
            headers=self.get_api_headers('john@example.com', 'dog'))
        self.assertEqual(response.status_code, 401)

    def test_token_auth(self):
        # add a user
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u = User(email='john@example.com', password='cat', confirmed=True,
                 role=r)
        db.session.add(u)
        db.session.commit()

        # issue a request with a bad token
        response = self.client.get(
            '/api/v1/posts/',
            headers=self.get_api_headers('bad-token', ''))
        self.assertEqual(response.status_code, 401)

        # get a token
        response = self.client.post(
            '/api/v1/tokens/',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertIsNotNone(json_response.get('token'))
        token = json_response['token']

        # issue a request with the token
        response = self.client.get(
            '/api/v1/posts/',
            headers=self.get_api_headers(token, ''))
        self.assertEqual(response.status_code, 200)

    def test_anonymous(self):
        response = self.client.get(
            '/api/v1/posts/',
            headers=self.get_api_headers('', ''))
        self.assertEqual(response.status_code, 401)

    def test_unconfirmed_account(self):
        # add an unconfirmed user
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u = User(email='john@example.com', password='cat', confirmed=False,
                 role=r)
        db.session.add(u)
        db.session.commit()

        # get list of posts with the unconfirmed account
        response = self.client.get(
            '/api/v1/posts/',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 403)

    def test_posts(self):
        # add a user
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u = User(email='john@example.com', password='cat', confirmed=True,
                 role=r)
        db.session.add(u)
        db.session.commit()

        # write an empty post
        response = self.client.post(
            '/api/v1/posts/',
            headers=self.get_api_headers('john@example.com', 'cat'),
            data=json.dumps({'body': ''}))
        self.assertEqual(response.status_code, 400)

        # write a post
        response = self.client.post(
            '/api/v1/posts/',
            headers=self.get_api_headers('john@example.com', 'cat'),
            data=json.dumps({'body': 'body of the *blog* post'}))
        self.assertEqual(response.status_code, 201)
        url = response.headers.get('Location')
        self.assertIsNotNone(url)

        # get the new post
        response = self.client.get(
            url,
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual('http://localhost' + json_response['url'], url)
        self.assertEqual(json_response['body'], 'body of the *blog* post')
        self.assertEqual(json_response['body_html'],
                        '<p>body of the <em>blog</em> post</p>')
        json_post = json_response

        # get the post from the user
        response = self.client.get(
            '/api/v1/users/{}/posts/'.format(u.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertIsNotNone(json_response.get('posts'))
        self.assertEqual(json_response.get('count', 0), 1)
        self.assertEqual(json_response['posts'][0], json_post)

        # get the post from the user as a follower
        response = self.client.get(
            '/api/v1/users/{}/timeline/'.format(u.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertIsNotNone(json_response.get('posts'))
        self.assertEqual(json_response.get('count', 0), 1)
        self.assertEqual(json_response['posts'][0], json_post)

        # edit post
        response = self.client.put(
            url,
            headers=self.get_api_headers('john@example.com', 'cat'),
            data=json.dumps({'body': 'updated body'}))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual('http://localhost' + json_response['url'], url)
        self.assertEqual(json_response['body'], 'updated body')
        self.assertEqual(json_response['body_html'], '<p>updated body</p>')

    def test_users(self):
        # add two users
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u1 = User(email='john@example.com', username='john',
                  password='cat', confirmed=True, role=r)
        u2 = User(email='susan@example.com', username='susan',
                  password='dog', confirmed=True, role=r)
        db.session.add_all([u1, u2])
        db.session.commit()

        # get users
        response = self.client.get(
            '/api/v1/users/{}'.format(u1.id),
            headers=self.get_api_headers('susan@example.com', 'dog'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['username'], 'john')
        response = self.client.get(
            '/api/v1/users/{}'.format(u2.id),
            headers=self.get_api_headers('susan@example.com', 'dog'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['username'], 'susan')

    def test_comments(self):
        # add two users
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u1 = User(email='john@example.com', username='john',
                  password='cat', confirmed=True, role=r)
        u2 = User(email='susan@example.com', username='susan',
                  password='dog', confirmed=True, role=r)
        db.session.add_all([u1, u2])
        db.session.commit()

        # add a post
        post = Post(body='body of the post', author=u1)
        db.session.add(post)
        db.session.commit()

        # write a comment
        response = self.client.post(
            '/api/v1/posts/{}/comments/'.format(post.id),
            headers=self.get_api_headers('susan@example.com', 'dog'),
            data=json.dumps({'body': 'Good [post](http://example.com)!'}))
        self.assertEqual(response.status_code, 201)
        json_response = json.loads(response.get_data(as_text=True))
        url = response.headers.get('Location')
        self.assertIsNotNone(url)
        self.assertEqual(json_response['body'],
                        'Good [post](http://example.com)!')
        self.assertEqual(
            re.sub('<.*?>', '', json_response['body_html']), 'Good post!')

        # get the new comment
        response = self.client.get(
            url,
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual('http://localhost' + json_response['url'], url)
        self.assertEqual(json_response['body'],
                        'Good [post](http://example.com)!')

        # add another comment
        comment = Comment(body='Thank you!', author=u1, post=post)
        db.session.add(comment)
        db.session.commit()

        # get the two comments from the post
        response = self.client.get(
            '/api/v1/posts/{}/comments/'.format(post.id),
            headers=self.get_api_headers('susan@example.com', 'dog'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertIsNotNone(json_response.get('comments'))
        self.assertEqual(json_response.get('count', 0), 2)

        # get all the comments
        response = self.client.get(
            '/api/v1/posts/{}/comments/'.format(post.id),
            headers=self.get_api_headers('susan@example.com', 'dog'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertIsNotNone(json_response.get('comments'))
        self.assertEqual(json_response.get('count', 0), 2)

    def _create_test_user(self):
        r = Role.query.filter_by(name='User').first()
        u = User(email='john@example.com', username='john',
                 password='cat', confirmed=True, role=r)
        db.session.add(u)
        db.session.commit()
        return u

    def test_posts_default_pagination(self):
        u = self._create_test_user()
        for i in range(5):
            post = Post(body='post {}'.format(i), author=u)
            db.session.add(post)
        db.session.commit()

        # default per_page is 20, so all 5 posts fit on one page
        response = self.client.get(
            '/api/v1/posts/',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 5)
        self.assertIsNone(json_response['prev'])
        self.assertIsNone(json_response['next'])

    def test_posts_custom_per_page(self):
        u = self._create_test_user()
        for i in range(5):
            post = Post(body='post {}'.format(i), author=u)
            db.session.add(post)
        db.session.commit()

        # request with per_page=2
        response = self.client.get(
            '/api/v1/posts/?per_page=2',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 2)
        self.assertIsNone(json_response['prev'])
        self.assertIsNotNone(json_response['next'])

        # page 2
        response = self.client.get(
            '/api/v1/posts/?page=2&per_page=2',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 2)
        self.assertIsNotNone(json_response['prev'])
        self.assertIsNotNone(json_response['next'])

        # page 3 (last page, 1 item)
        response = self.client.get(
            '/api/v1/posts/?page=3&per_page=2',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 1)
        self.assertIsNotNone(json_response['prev'])
        self.assertIsNone(json_response['next'])

    def test_posts_per_page_too_large(self):
        u = self._create_test_user()
        for i in range(5):
            post = Post(body='post {}'.format(i), author=u)
            db.session.add(post)
        db.session.commit()

        # per_page exceeding max should fall back to default (20)
        response = self.client.get(
            '/api/v1/posts/?per_page=9999',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 5)

    def test_posts_per_page_invalid(self):
        u = self._create_test_user()
        for i in range(5):
            post = Post(body='post {}'.format(i), author=u)
            db.session.add(post)
        db.session.commit()

        # per_page=0 should fall back to default
        response = self.client.get(
            '/api/v1/posts/?per_page=0',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(json_response['posts']), 5)

        # per_page=-1 should fall back to default
        response = self.client.get(
            '/api/v1/posts/?per_page=-1',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(json_response['posts']), 5)

        # non-integer per_page should fall back to default (Flask type=int
        # returns default for non-integer values)
        response = self.client.get(
            '/api/v1/posts/?per_page=abc',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(json_response['posts']), 5)

    def test_pagination_links_preserve_per_page(self):
        u = self._create_test_user()
        for i in range(5):
            post = Post(body='post {}'.format(i), author=u)
            db.session.add(post)
        db.session.commit()

        # with per_page specified, links should preserve it
        response = self.client.get(
            '/api/v1/posts/?per_page=2',
            headers=self.get_api_headers('john@example.com', 'cat'))
        json_response = json.loads(response.get_data(as_text=True))
        self.assertIn('per_page=2', json_response['next'])

        # page 2: both prev and next should have per_page
        response = self.client.get(
            '/api/v1/posts/?page=2&per_page=2',
            headers=self.get_api_headers('john@example.com', 'cat'))
        json_response = json.loads(response.get_data(as_text=True))
        self.assertIn('per_page=2', json_response['prev'])
        self.assertIn('per_page=2', json_response['next'])

        # without per_page, links should NOT contain per_page
        # create enough posts to exceed default per_page
        for i in range(20):
            post = Post(body='extra post {}'.format(i), author=u)
            db.session.add(post)
        db.session.commit()

        response = self.client.get(
            '/api/v1/posts/',
            headers=self.get_api_headers('john@example.com', 'cat'))
        json_response = json.loads(response.get_data(as_text=True))
        self.assertIsNotNone(json_response['next'])
        self.assertNotIn('per_page', json_response['next'])

    def test_comments_custom_per_page(self):
        u = self._create_test_user()
        post = Post(body='test post', author=u)
        db.session.add(post)
        db.session.commit()

        for i in range(5):
            c = Comment(body='comment {}'.format(i), author=u, post=post)
            db.session.add(c)
        db.session.commit()

        # global comments with per_page=2
        response = self.client.get(
            '/api/v1/comments/?per_page=2',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['comments']), 2)
        self.assertIn('per_page=2', json_response['next'])

        # post comments with per_page=2
        response = self.client.get(
            '/api/v1/posts/{}/comments/?per_page=2'.format(post.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['comments']), 2)
        self.assertIn('per_page=2', json_response['next'])

    def test_user_posts_custom_per_page(self):
        u = self._create_test_user()
        for i in range(5):
            post = Post(body='post {}'.format(i), author=u)
            db.session.add(post)
        db.session.commit()

        # user posts with per_page=2
        response = self.client.get(
            '/api/v1/users/{}/posts/?per_page=2'.format(u.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 2)
        self.assertIn('per_page=2', json_response['next'])

    def test_timeline_custom_per_page(self):
        u = self._create_test_user()
        for i in range(5):
            post = Post(body='post {}'.format(i), author=u)
            db.session.add(post)
        db.session.commit()

        # timeline with per_page=2
        response = self.client.get(
            '/api/v1/users/{}/timeline/?per_page=2'.format(u.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(json_response['posts']), 2)
        self.assertIn('per_page=2', json_response['next'])
