from flask import jsonify, request, current_app, url_for
from . import api
from ..models import User, Post


def _resolve_author(author_param):
    """Resolve a User from an author query parameter (ID or username).

    Returns the User if found, or None if the parameter is provided but no
    matching user exists.  Returns the sentinel value ``'not_provided'`` when
    the caller did not supply a filter at all, so endpoints can distinguish
    "no filter" from "filter matched nobody".
    """
    if author_param is None:
        return 'not_provided'
    try:
        author_id = int(author_param)
        return User.query.get(author_id)
    except (ValueError, TypeError):
        return User.query.filter_by(username=author_param).first()


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
    author_param = request.args.get('author')
    author = _resolve_author(author_param)

    query = user.followed_posts.order_by(Post.timestamp.desc())
    if author_param is not None:
        if author is None:
            # Author filter specified but not found — return empty result set.
            return jsonify({'posts': [], 'prev': None, 'next': None, 'count': 0})
        query = query.filter(Post.author_id == author.id)

    pagination = query.paginate(
        page=page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_user_followed_posts', id=id, page=page-1,
                       author=author_param)
    next = None
    if pagination.has_next:
        next = url_for('api.get_user_followed_posts', id=id, page=page+1,
                       author=author_param)
    return jsonify({
        'posts': [post.to_json() for post in posts],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })
