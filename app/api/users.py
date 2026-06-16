from flask import jsonify, request, current_app, url_for
from . import api
from ..models import User, Post
from .utils import paginate_query


@api.route('/users/<int:id>')
def get_user(id):
    user = User.query.get_or_404(id)
    return jsonify(user.to_json())


@api.route('/users/<int:id>/posts/')
def get_user_posts(id):
    user = User.query.get_or_404(id)
    return paginate_query(
        user.posts.order_by(Post.timestamp.desc()),
        'api.get_user_posts', 'FLASKY_POSTS_PER_PAGE', 'posts',
        id=id)


@api.route('/users/<int:id>/timeline/')
def get_user_followed_posts(id):
    user = User.query.get_or_404(id)
    return paginate_query(
        user.followed_posts.order_by(Post.timestamp.desc()),
        'api.get_user_followed_posts', 'FLASKY_POSTS_PER_PAGE', 'posts',
        id=id)
