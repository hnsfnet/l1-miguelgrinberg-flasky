from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import Post, Permission, Comment
from . import api
from .decorators import permission_required
from .utils import paginate_query


@api.route('/comments/')
def get_comments():
    return paginate_query(
        Comment.query.order_by(Comment.timestamp.desc()),
        'api.get_comments', 'FLASKY_COMMENTS_PER_PAGE', 'comments')


@api.route('/comments/<int:id>')
def get_comment(id):
    comment = Comment.query.get_or_404(id)
    return jsonify(comment.to_json())


@api.route('/posts/<int:id>/comments/')
def get_post_comments(id):
    post = Post.query.get_or_404(id)
    return paginate_query(
        post.comments.order_by(Comment.timestamp.asc()),
        'api.get_post_comments', 'FLASKY_COMMENTS_PER_PAGE', 'comments',
        id=id)


@api.route('/posts/<int:id>/comments/', methods=['POST'])
@permission_required(Permission.COMMENT)
def new_post_comment(id):
    post = Post.query.get_or_404(id)
    comment = Comment.from_json(request.json)
    comment.author = g.current_user
    comment.post = post
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment.to_json()), 201, \
        {'Location': url_for('api.get_comment', id=comment.id)}
