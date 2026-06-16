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

    def _create_user(self, email='john@example.com', username='john',
                     password='cat'):
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u = User(email=email, username=username, password=password,
                 confirmed=True, role=r)
        db.session.add(u)
        db.session.commit()
        return u

    def _create_posts(self, author, count):
        posts = []
        for i in range(count):
            p = Post(body='post body {}'.format(i), author=author)
            db.session.add(p)
            posts.append(p)
        db.session.commit()
        return posts

    def _create_comments(self, post, author, count):
        comments = []
        for i in range(count):
            c = Comment(body='comment {}'.format(i), author=author, post=post)
            db.session.add(c)
            comments.append(c)
        db.session.commit()
        return comments

    def test_posts_default_pagination(self):
        u = self._create_user()
        # Default FLASKY_POSTS_PER_PAGE is 20; create 25 posts
        self._create_posts(u, 25)

        # page 1 without per_page should return 20 items
        response = self.client.get(
            '/api/v1/posts/',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['posts']), 20)
        self.assertEqual(data['count'], 25)
        self.assertIsNone(data['prev'])
        self.assertIsNotNone(data['next'])
        self.assertIn('page=2', data['next'])

    def test_posts_custom_per_page(self):
        u = self._create_user()
        self._create_posts(u, 15)

        # per_page=5 should return 5 items on page 1
        response = self.client.get(
            '/api/v1/posts/?per_page=5',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['posts']), 5)
        self.assertEqual(data['count'], 15)
        self.assertIsNone(data['prev'])
        self.assertIsNotNone(data['next'])
        # next link must carry per_page=5
        self.assertIn('per_page=5', data['next'])
        self.assertIn('page=2', data['next'])

        # page 2 with per_page=5
        response = self.client.get(
            '/api/v1/posts/?per_page=5&page=2',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['posts']), 5)
        self.assertIsNotNone(data['prev'])
        self.assertIsNotNone(data['next'])
        self.assertIn('per_page=5', data['prev'])
        self.assertIn('per_page=5', data['next'])

        # page 3 (last) with per_page=5
        response = self.client.get(
            '/api/v1/posts/?per_page=5&page=3',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['posts']), 5)
        self.assertIsNotNone(data['prev'])
        self.assertIsNone(data['next'])

    def test_posts_per_page_oversized(self):
        u = self._create_user()
        self._create_posts(u, 5)

        # per_page=9999 should be clamped to FLASKY_API_PER_PAGE_MAX (100)
        response = self.client.get(
            '/api/v1/posts/?per_page=9999',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        # All 5 posts returned since 5 < 100
        self.assertEqual(len(data['posts']), 5)
        self.assertEqual(data['count'], 5)
        self.assertIsNone(data['prev'])
        self.assertIsNone(data['next'])

    def test_posts_per_page_invalid(self):
        u = self._create_user()
        self._create_posts(u, 3)

        # per_page=abc should fall back to default
        response = self.client.get(
            '/api/v1/posts/?per_page=abc',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['posts']), 3)
        self.assertEqual(data['count'], 3)

        # per_page=0 should also fall back to default
        response = self.client.get(
            '/api/v1/posts/?per_page=0',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['posts']), 3)

        # per_page=-5 should also fall back to default
        response = self.client.get(
            '/api/v1/posts/?per_page=-5',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['posts']), 3)

    def test_comments_default_pagination(self):
        u = self._create_user()
        post = Post(body='a post', author=u)
        db.session.add(post)
        db.session.commit()
        # Default FLASKY_COMMENTS_PER_PAGE is 30; create 35 comments
        self._create_comments(post, u, 35)

        response = self.client.get(
            '/api/v1/comments/',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['comments']), 30)
        self.assertEqual(data['count'], 35)
        self.assertIsNone(data['prev'])
        self.assertIsNotNone(data['next'])

    def test_comments_custom_per_page(self):
        u = self._create_user()
        post = Post(body='a post', author=u)
        db.session.add(post)
        db.session.commit()
        self._create_comments(post, u, 12)

        # per_page=5 on global comments list
        response = self.client.get(
            '/api/v1/comments/?per_page=5',
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['comments']), 5)
        self.assertEqual(data['count'], 12)
        self.assertIn('per_page=5', data['next'])

    def test_post_comments_custom_per_page(self):
        u = self._create_user()
        post = Post(body='a post', author=u)
        db.session.add(post)
        db.session.commit()
        self._create_comments(post, u, 8)

        # per_page=3 on post comments list
        response = self.client.get(
            '/api/v1/posts/{}/comments/?per_page=3'.format(post.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['comments']), 3)
        self.assertEqual(data['count'], 8)
        self.assertIn('per_page=3', data['next'])

    def test_user_posts_custom_per_page(self):
        u = self._create_user()
        self._create_posts(u, 10)

        response = self.client.get(
            '/api/v1/users/{}/posts/?per_page=4'.format(u.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['posts']), 4)
        self.assertEqual(data['count'], 10)
        self.assertIn('per_page=4', data['next'])

    def test_timeline_custom_per_page(self):
        u = self._create_user()
        self._create_posts(u, 10)

        response = self.client.get(
            '/api/v1/users/{}/timeline/?per_page=3'.format(u.id),
            headers=self.get_api_headers('john@example.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['posts']), 3)
        self.assertEqual(data['count'], 10)
        self.assertIn('per_page=3', data['next'])
