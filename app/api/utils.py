from flask import request, current_app, url_for, jsonify


def paginate_query(query, endpoint, default_per_page_key, item_name,
                   **endpoint_kwargs):
    page = request.args.get('page', 1, type=int)
    default_per_page = current_app.config[default_per_page_key]
    per_page = request.args.get('per_page', default_per_page, type=int)
    max_per_page = current_app.config['FLASKY_MAX_PER_PAGE']
    if per_page < 1 or per_page > max_per_page:
        per_page = default_per_page
    pagination = query.paginate(page=page, per_page=per_page,
                                error_out=False)
    link_kwargs = dict(endpoint_kwargs)
    if 'per_page' in request.args:
        link_kwargs['per_page'] = per_page
    prev = None
    if pagination.has_prev:
        prev = url_for(endpoint, page=page - 1, **link_kwargs)
    next_url = None
    if pagination.has_next:
        next_url = url_for(endpoint, page=page + 1, **link_kwargs)
    return jsonify({
        item_name: [item.to_json() for item in pagination.items],
        'prev': prev,
        'next': next_url,
        'count': pagination.total
    })
