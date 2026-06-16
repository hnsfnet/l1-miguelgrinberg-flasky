from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import Post, Permission, User
from . import api
from .decorators import permission_required
from .errors import forbidden


@api.route('/posts/')
def get_posts():
    page = request.args.get('page', 1, type=int)
    author_id = request.args.get('author_id', type=int)
    author_username = request.args.get('author_username', type=str)

    query = Post.query
    filter_kwargs = {}
    if author_username:
        author = User.query.filter_by(username=author_username).first()
        if author is None:
            return jsonify({'posts': [], 'prev': None,
                            'next': None, 'count': 0})
        filter_kwargs['author_username'] = author_username
        query = query.filter_by(author_id=author.id)
    elif author_id:
        author = User.query.get(author_id)
        if author is None:
            return jsonify({'posts': [], 'prev': None,
                            'next': None, 'count': 0})
        filter_kwargs['author_id'] = author_id
        query = query.filter_by(author_id=author_id)

    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_posts', page=page-1, **filter_kwargs)
    next = None
    if pagination.has_next:
        next = url_for('api.get_posts', page=page+1, **filter_kwargs)
    return jsonify({
        'posts': [post.to_json() for post in posts],
        'prev': prev,
        'next': next,
        'count': pagination.total
    })


@api.route('/posts/<int:id>')
def get_post(id):
    post = Post.query.get_or_404(id)
    return jsonify(post.to_json())


@api.route('/posts/', methods=['POST'])
@permission_required(Permission.WRITE)
def new_post():
    post = Post.from_json(request.json)
    post.author = g.current_user
    db.session.add(post)
    db.session.commit()
    return jsonify(post.to_json()), 201, \
        {'Location': url_for('api.get_post', id=post.id)}


@api.route('/posts/<int:id>', methods=['PUT'])
@permission_required(Permission.WRITE)
def edit_post(id):
    post = Post.query.get_or_404(id)
    if g.current_user != post.author and \
            not g.current_user.can(Permission.ADMIN):
        return forbidden('Insufficient permissions')
    post.body = request.json.get('body', post.body)
    db.session.add(post)
    db.session.commit()
    return jsonify(post.to_json())
