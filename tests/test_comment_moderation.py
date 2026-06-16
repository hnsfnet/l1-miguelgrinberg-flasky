import unittest
import json
from base64 import b64encode
from app import create_app, db
from app.models import User, Role, Post, Comment, Permission


class CommentVisibilityWebTestCase(unittest.TestCase):
    """Tests for comment visibility on web views (post detail page)."""

    def setUp(self):
        self.app = create_app('testing')
        self.app.config['FLASKY_COMMENTS_PER_PAGE'] = 3
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _create_user(self, email, username, password, role_name='User'):
        r = Role.query.filter_by(name=role_name).first()
        u = User(email=email, username=username, password=password,
                 confirmed=True, role=r)
        db.session.add(u)
        db.session.commit()
        return u

    def _login(self, email, password):
        self.client.post('/auth/login', data={
            'email': email,
            'password': password,
        })

    def _create_post_with_comments(self, author):
        """Create a post with 3 normal + 2 disabled comments."""
        post = Post(body='Test post', author=author)
        db.session.add(post)
        db.session.commit()

        comments = []
        for i in range(3):
            c = Comment(body='visible comment {}'.format(i),
                        author=author, post=post, disabled=False)
            db.session.add(c)
            comments.append(c)
        for i in range(2):
            c = Comment(body='disabled comment {}'.format(i),
                        author=author, post=post, disabled=True)
            db.session.add(c)
            comments.append(c)
        db.session.commit()
        return post, comments

    def test_regular_user_cannot_see_disabled_comments(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        post, _ = self._create_post_with_comments(user)

        self._login('user@test.com', 'cat')
        response = self.client.get('/post/{}'.format(post.id))
        data = response.get_data(as_text=True)

        self.assertIn('visible comment 0', data)
        self.assertIn('visible comment 1', data)
        self.assertIn('visible comment 2', data)
        self.assertNotIn('disabled comment 0', data)
        self.assertNotIn('disabled comment 1', data)
        self.assertNotIn('This comment has been disabled by a moderator', data)

    def test_moderator_can_see_disabled_comments(self):
        mod = self._create_user('mod@test.com', 'mod', 'cat',
                                role_name='Moderator')
        post, _ = self._create_post_with_comments(mod)

        self._login('mod@test.com', 'cat')
        response = self.client.get('/post/{}'.format(post.id))
        data = response.get_data(as_text=True)

        self.assertIn('visible comment 0', data)
        self.assertIn('disabled comment 0', data)
        self.assertIn('This comment has been disabled by a moderator', data)
        self.assertIn('Enable', data)

    def test_pagination_excludes_disabled_for_regular_user(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        post = Post(body='Test post', author=user)
        db.session.add(post)
        db.session.commit()

        # 4 visible + 3 disabled = 7 total, but only 4 visible
        # With per_page=3, regular user should see 2 pages (ceil(4/3))
        for i in range(4):
            db.session.add(Comment(body='vis {}'.format(i),
                                   author=user, post=post, disabled=False))
        for i in range(3):
            db.session.add(Comment(body='dis {}'.format(i),
                                   author=user, post=post, disabled=True))
        db.session.commit()

        self._login('user@test.com', 'cat')
        response = self.client.get('/post/{}?page=1'.format(post.id))
        data = response.get_data(as_text=True)
        # Page 1 should have 3 visible comments
        self.assertIn('vis 0', data)
        self.assertIn('vis 1', data)
        self.assertIn('vis 2', data)
        self.assertNotIn('vis 3', data)

        response = self.client.get('/post/{}?page=2'.format(post.id))
        data = response.get_data(as_text=True)
        # Page 2 should have 1 visible comment
        self.assertIn('vis 3', data)

        # No disabled comments on any page
        self.assertNotIn('dis 0', data)

    def test_pagination_includes_disabled_for_moderator(self):
        mod = self._create_user('mod@test.com', 'mod', 'cat',
                                role_name='Moderator')
        post = Post(body='Test post', author=mod)
        db.session.add(post)
        db.session.commit()

        # 4 visible + 3 disabled = 7 total
        # With per_page=3, moderator should see 3 pages (ceil(7/3))
        for i in range(4):
            db.session.add(Comment(body='vis {}'.format(i),
                                   author=mod, post=post, disabled=False))
        for i in range(3):
            db.session.add(Comment(body='dis {}'.format(i),
                                   author=mod, post=post, disabled=True))
        db.session.commit()

        self._login('mod@test.com', 'cat')
        response = self.client.get('/post/{}?page=3'.format(post.id))
        data = response.get_data(as_text=True)
        # Page 3 should exist and have the last comment
        self.assertIn('dis 2', data)

    def test_anonymous_user_cannot_see_disabled_comments(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        post, _ = self._create_post_with_comments(user)

        response = self.client.get('/post/{}'.format(post.id))
        data = response.get_data(as_text=True)

        self.assertIn('visible comment 0', data)
        self.assertNotIn('disabled comment 0', data)

    def test_visible_comment_count_on_post_listing(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        post, _ = self._create_post_with_comments(user)

        self._login('user@test.com', 'cat')
        response = self.client.get('/')
        data = response.get_data(as_text=True)

        # 3 visible comments out of 5 total
        self.assertIn('3 Comments', data)
        self.assertNotIn('5 Comments', data)


class CommentVisibilityAPITestCase(unittest.TestCase):
    """Tests for comment visibility on API endpoints."""

    def setUp(self):
        self.app = create_app('testing')
        self.app.config['FLASKY_COMMENTS_PER_PAGE'] = 3
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Role.insert_roles()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _headers(self, email, password):
        return {
            'Authorization': 'Basic ' + b64encode(
                (email + ':' + password).encode('utf-8')).decode('utf-8'),
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def _create_user(self, email, username, password, role_name='User'):
        r = Role.query.filter_by(name=role_name).first()
        u = User(email=email, username=username, password=password,
                 confirmed=True, role=r)
        db.session.add(u)
        db.session.commit()
        return u

    def _create_post_with_comments(self, author):
        post = Post(body='Test post', author=author)
        db.session.add(post)
        db.session.commit()

        visible_comments = []
        disabled_comments = []
        for i in range(3):
            c = Comment(body='visible {}'.format(i),
                        author=author, post=post, disabled=False)
            db.session.add(c)
            visible_comments.append(c)
        for i in range(2):
            c = Comment(body='disabled {}'.format(i),
                        author=author, post=post, disabled=True)
            db.session.add(c)
            disabled_comments.append(c)
        db.session.commit()
        return post, visible_comments, disabled_comments

    # --- GET /api/v1/posts/<id>/comments/ ---

    def test_post_comments_filters_disabled_for_regular_user(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        post, _, _ = self._create_post_with_comments(user)

        response = self.client.get(
            '/api/v1/posts/{}/comments/'.format(post.id),
            headers=self._headers('user@test.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))

        self.assertEqual(data['count'], 3)
        bodies = [c['body'] for c in data['comments']]
        self.assertIn('visible 0', bodies)
        self.assertNotIn('disabled 0', bodies)

    def test_post_comments_includes_disabled_for_moderator(self):
        mod = self._create_user('mod@test.com', 'mod', 'cat',
                                role_name='Moderator')
        post, _, _ = self._create_post_with_comments(mod)

        response = self.client.get(
            '/api/v1/posts/{}/comments/'.format(post.id),
            headers=self._headers('mod@test.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))

        self.assertEqual(data['count'], 5)
        bodies = [c['body'] for c in data['comments']]
        self.assertIn('visible 0', bodies)
        self.assertIn('disabled 0', bodies)

    def test_post_comments_pagination_for_regular_user(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        post = Post(body='Test', author=user)
        db.session.add(post)
        db.session.commit()

        # 4 visible + 3 disabled
        for i in range(4):
            db.session.add(Comment(body='v{}'.format(i),
                                   author=user, post=post, disabled=False))
        for i in range(3):
            db.session.add(Comment(body='d{}'.format(i),
                                   author=user, post=post, disabled=True))
        db.session.commit()

        # Page 1: 3 comments, page 2: 1 comment
        resp = self.client.get(
            '/api/v1/posts/{}/comments/?page=1'.format(post.id),
            headers=self._headers('user@test.com', 'cat'))
        data = json.loads(resp.get_data(as_text=True))
        self.assertEqual(data['count'], 4)
        self.assertEqual(len(data['comments']), 3)
        self.assertIsNotNone(data['next'])

        resp = self.client.get(
            '/api/v1/posts/{}/comments/?page=2'.format(post.id),
            headers=self._headers('user@test.com', 'cat'))
        data = json.loads(resp.get_data(as_text=True))
        self.assertEqual(len(data['comments']), 1)
        self.assertIsNone(data['next'])

    # --- GET /api/v1/comments/ ---

    def test_global_comments_filters_disabled_for_regular_user(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        _, _, _ = self._create_post_with_comments(user)

        response = self.client.get(
            '/api/v1/comments/',
            headers=self._headers('user@test.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))

        self.assertEqual(data['count'], 3)
        bodies = [c['body'] for c in data['comments']]
        self.assertNotIn('disabled 0', bodies)

    def test_global_comments_includes_disabled_for_moderator(self):
        mod = self._create_user('mod@test.com', 'mod', 'cat',
                                role_name='Moderator')
        _, _, _ = self._create_post_with_comments(mod)

        response = self.client.get(
            '/api/v1/comments/',
            headers=self._headers('mod@test.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))

        self.assertEqual(data['count'], 5)

    # --- GET /api/v1/comments/<id> ---

    def test_get_disabled_comment_forbidden_for_regular_user(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        _, _, disabled = self._create_post_with_comments(user)

        response = self.client.get(
            '/api/v1/comments/{}'.format(disabled[0].id),
            headers=self._headers('user@test.com', 'cat'))
        self.assertEqual(response.status_code, 403)

    def test_get_disabled_comment_allowed_for_moderator(self):
        mod = self._create_user('mod@test.com', 'mod', 'cat',
                                role_name='Moderator')
        _, _, disabled = self._create_post_with_comments(mod)

        response = self.client.get(
            '/api/v1/comments/{}'.format(disabled[0].id),
            headers=self._headers('mod@test.com', 'cat'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['body'], 'disabled 0')

    def test_get_normal_comment_ok_for_regular_user(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        _, visible, _ = self._create_post_with_comments(user)

        response = self.client.get(
            '/api/v1/comments/{}'.format(visible[0].id),
            headers=self._headers('user@test.com', 'cat'))
        self.assertEqual(response.status_code, 200)

    # --- disabled field in JSON ---

    def test_comment_json_includes_disabled_field(self):
        user = self._create_user('user@test.com', 'user', 'cat')
        _, visible, _ = self._create_post_with_comments(user)

        response = self.client.get(
            '/api/v1/comments/{}'.format(visible[0].id),
            headers=self._headers('user@test.com', 'cat'))
        data = json.loads(response.get_data(as_text=True))
        self.assertIn('disabled', data)
        self.assertFalse(data['disabled'])

    def test_disabled_comment_json_shows_disabled_true_for_moderator(self):
        mod = self._create_user('mod@test.com', 'mod', 'cat',
                                role_name='Moderator')
        _, _, disabled = self._create_post_with_comments(mod)

        response = self.client.get(
            '/api/v1/comments/{}'.format(disabled[0].id),
            headers=self._headers('mod@test.com', 'cat'))
        data = json.loads(response.get_data(as_text=True))
        self.assertTrue(data['disabled'])
