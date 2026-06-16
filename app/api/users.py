from flask import jsonify, request, current_app, url_for
from . import api
from ..models import User, Post
from .pagination import get_per_page, pagination_links


@api.route('/users/<int:id>')
def get_user(id):
    user = User.query.get_or_404(id)
    return jsonify(user.to_json())


@api.route('/users/<int:id>/posts/')
def get_user_posts(id):
    user = User.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    per_page = get_per_page('FLASKY_POSTS_PER_PAGE')
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=per_page,
        error_out=False)
    posts = pagination.items
    prev, next = pagination_links('api.get_user_posts', page, per_page, pagination, id=id)
    return jsonify({
        'posts': [post.to_json() for post in posts],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })


@api.route('/users/<int:id>/timeline/')
def get_user_followed_posts(id):
    user = User.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    per_page = get_per_page('FLASKY_POSTS_PER_PAGE')
    pagination = user.followed_posts.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=per_page,
        error_out=False)
    posts = pagination.items
    prev, next = pagination_links('api.get_user_followed_posts', page, per_page, pagination, id=id)
    return jsonify({
        'posts': [post.to_json() for post in posts],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })
