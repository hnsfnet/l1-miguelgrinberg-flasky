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

    def test_posts_author_filter(self):
        # add two users
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u1 = User(email='john@example.com', username='john',
                  password='cat', confirmed=True, role=r)
        u2 = User(email='susan@example.com', username='susan',
                  password='dog', confirmed=True, role=r)
        db.session.add_all([u1, u2])
        db.session.commit()

        # create posts for each user
        p1 = Post(body='post by john 1', author=u1)
        p2 = Post(body='post by john 2', author=u1)
        p3 = Post(body='post by susan', author=u2)
        db.session.add_all([p1, p2, p3])
        db.session.commit()

        headers = self.get_api_headers('john@example.com', 'cat')

        # no filter — returns all posts
        response = self.client.get('/api/v1/posts/', headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 3)
        self.assertEqual(len(json_response['posts']), 3)

        # filter by author username
        response = self.client.get('/api/v1/posts/?author=john',
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 2)
        self.assertEqual(len(json_response['posts']), 2)
        expected_author_url = '/api/v1/users/{}'.format(u1.id)
        for post in json_response['posts']:
            self.assertIn(expected_author_url, post['author_url'])

        # filter by author ID
        response = self.client.get(
            '/api/v1/posts/?author={}'.format(u2.id), headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 1)
        self.assertEqual(len(json_response['posts']), 1)
        self.assertEqual(json_response['posts'][0]['body'], 'post by susan')

        # filter by non-existent author — empty result, not full list
        response = self.client.get('/api/v1/posts/?author=ghost',
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 0)
        self.assertEqual(json_response['posts'], [])
        self.assertIsNone(json_response['prev'])
        self.assertIsNone(json_response['next'])

        # filter by non-existent author ID
        response = self.client.get('/api/v1/posts/?author=9999',
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 0)
        self.assertEqual(json_response['posts'], [])

    def test_posts_author_filter_pagination(self):
        # use a small page size to force pagination
        self.app.config['FLASKY_POSTS_PER_PAGE'] = 2

        r = Role.query.filter_by(name='User').first()
        u = User(email='john@example.com', username='john',
                 password='cat', confirmed=True, role=r)
        db.session.add(u)
        db.session.commit()

        # create 5 posts for john
        for i in range(5):
            db.session.add(Post(body='john post {}'.format(i), author=u))
        db.session.commit()

        headers = self.get_api_headers('john@example.com', 'cat')

        # page 1 with author filter — should have next, no prev
        response = self.client.get('/api/v1/posts/?author=john',
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 2)
        self.assertIsNone(json_response['prev'])
        self.assertIsNotNone(json_response['next'])
        self.assertIn('author=john', json_response['next'])

        # page 2 with author filter — should have prev and next
        response = self.client.get('/api/v1/posts/?author=john&page=2',
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 2)
        self.assertIsNotNone(json_response['prev'])
        self.assertIsNotNone(json_response['next'])
        self.assertIn('author=john', json_response['prev'])
        self.assertIn('author=john', json_response['next'])

        # page 3 with author filter — should have prev, no next
        response = self.client.get('/api/v1/posts/?author=john&page=3',
                                   headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 1)
        self.assertIsNotNone(json_response['prev'])
        self.assertIsNone(json_response['next'])
        self.assertIn('author=john', json_response['prev'])

    def test_timeline_author_filter(self):
        # add three users
        r = Role.query.filter_by(name='User').first()
        self.assertIsNotNone(r)
        u1 = User(email='john@example.com', username='john',
                  password='cat', confirmed=True, role=r)
        u2 = User(email='susan@example.com', username='susan',
                  password='dog', confirmed=True, role=r)
        u3 = User(email='mary@example.com', username='mary',
                  password='fish', confirmed=True, role=r)
        db.session.add_all([u1, u2, u3])
        db.session.commit()

        # john follows susan (john already follows himself from __init__)
        u1.follow(u2)
        db.session.commit()

        # create posts for each user
        p1 = Post(body='john post', author=u1)
        p2 = Post(body='susan post', author=u2)
        p3 = Post(body='mary post', author=u3)
        db.session.add_all([p1, p2, p3])
        db.session.commit()

        headers = self.get_api_headers('john@example.com', 'cat')

        # no filter — timeline shows john's + susan's posts (not mary's)
        response = self.client.get(
            '/api/v1/users/{}/timeline/'.format(u1.id), headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 2)
        bodies = [p['body'] for p in json_response['posts']]
        self.assertIn('john post', bodies)
        self.assertIn('susan post', bodies)
        self.assertNotIn('mary post', bodies)

        # filter by susan — only susan's post in timeline
        response = self.client.get(
            '/api/v1/users/{}/timeline/?author=susan'.format(u1.id),
            headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 1)
        self.assertEqual(json_response['posts'][0]['body'], 'susan post')

        # filter by john — only john's own post in timeline
        response = self.client.get(
            '/api/v1/users/{}/timeline/?author=john'.format(u1.id),
            headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 1)
        self.assertEqual(json_response['posts'][0]['body'], 'john post')

        # filter by mary — mary is NOT in john's follow list, so empty result
        # even though mary has posts; the timeline must not expose them
        response = self.client.get(
            '/api/v1/users/{}/timeline/?author=mary'.format(u1.id),
            headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 0)
        self.assertEqual(json_response['posts'], [])

        # filter by non-existent author — empty result
        response = self.client.get(
            '/api/v1/users/{}/timeline/?author=ghost'.format(u1.id),
            headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 0)
        self.assertEqual(json_response['posts'], [])

        # filter by author ID (susan's id)
        response = self.client.get(
            '/api/v1/users/{}/timeline/?author={}'.format(u1.id, u2.id),
            headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 1)
        self.assertEqual(json_response['posts'][0]['body'], 'susan post')

    def test_timeline_author_filter_pagination(self):
        self.app.config['FLASKY_POSTS_PER_PAGE'] = 2

        r = Role.query.filter_by(name='User').first()
        u1 = User(email='john@example.com', username='john',
                  password='cat', confirmed=True, role=r)
        u2 = User(email='susan@example.com', username='susan',
                  password='dog', confirmed=True, role=r)
        db.session.add_all([u1, u2])
        db.session.commit()

        # john follows susan
        u1.follow(u2)
        db.session.commit()

        # susan writes 4 posts
        for i in range(4):
            db.session.add(Post(body='susan post {}'.format(i), author=u2))
        # john writes 1 post (should not appear when filtering by susan)
        db.session.add(Post(body='john post', author=u1))
        db.session.commit()

        headers = self.get_api_headers('john@example.com', 'cat')

        # page 1 filtering by susan — 4 results, page size 2
        response = self.client.get(
            '/api/v1/users/{}/timeline/?author=susan'.format(u1.id),
            headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 4)
        self.assertEqual(len(json_response['posts']), 2)
        self.assertIsNone(json_response['prev'])
        self.assertIsNotNone(json_response['next'])
        self.assertIn('author=susan', json_response['next'])

        # page 2 filtering by susan
        response = self.client.get(
            '/api/v1/users/{}/timeline/?author=susan&page=2'.format(u1.id),
            headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 4)
        self.assertEqual(len(json_response['posts']), 2)
        self.assertIsNotNone(json_response['prev'])
        self.assertIsNone(json_response['next'])
        self.assertIn('author=susan', json_response['prev'])

        # without filter, total should be 5 (4 susan + 1 john)
        response = self.client.get(
            '/api/v1/users/{}/timeline/'.format(u1.id),
            headers=headers)
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.get_data(as_text=True))
        self.assertEqual(json_response['count'], 5)
        self.assertEqual(len(json_response['posts']), 2)
