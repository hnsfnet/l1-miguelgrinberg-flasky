from flask import jsonify, request, current_app, url_for
from . import api
from ..models import User, Post


@api.route('/users/<int:id>')
def get_user(id):
    user = User.query.get_or_404(id)
    return jsonify(user.to_json())


@api.route('/users/<int:id>/posts/')
def get_user_posts(id):
    user = User.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_user_posts', id=id, page=page-1)
    next = None
    if pagination.has_next:
        next = url_for('api.get_user_posts', id=id, page=page+1)
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
    author_id = request.args.get('author_id', type=int)
    author_username = request.args.get('author_username', type=str)

    query = user.followed_posts
    filter_kwargs = {}
    if author_username:
        author = User.query.filter_by(username=author_username).first()
        if author is None:
            return jsonify({'posts': [], 'prev': None,
                            'next': None, 'count': 0})
        filter_kwargs['author_username'] = author_username
        query = query.filter(Post.author_id == author.id)
    elif author_id:
        author = User.query.get(author_id)
        if author is None:
            return jsonify({'posts': [], 'prev': None,
                            'next': None, 'count': 0})
        filter_kwargs['author_id'] = author_id
        query = query.filter(Post.author_id == author_id)

    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_user_followed_posts', id=id, page=page-1,
                        **filter_kwargs)
    next = None
    if pagination.has_next:
        next = url_for('api.get_user_followed_posts', id=id, page=page+1,
                        **filter_kwargs)
    return jsonify({
        'posts': [post.to_json() for post in posts],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })
