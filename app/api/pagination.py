from flask import request, current_app, url_for


def get_per_page(default_config_key):
    """Resolve the per_page value from the query string.

    Falls back to the given config key when the parameter is absent or
    invalid, and clamps the result to FLASKY_API_PER_PAGE_MAX.
    """
    default = current_app.config[default_config_key]
    max_per_page = current_app.config['FLASKY_API_PER_PAGE_MAX']
    try:
        per_page = int(request.args.get('per_page', default))
    except (ValueError, TypeError):
        per_page = default
    if per_page < 1:
        per_page = default
    if per_page > max_per_page:
        per_page = max_per_page
    return per_page


def pagination_links(endpoint, page, per_page, pagination, **kwargs):
    """Build prev/next URLs that preserve the per_page parameter."""
    prev = None
    if pagination.has_prev:
        prev = url_for(endpoint, page=page - 1, per_page=per_page, **kwargs)
    next = None
    if pagination.has_next:
        next = url_for(endpoint, page=page + 1, per_page=per_page, **kwargs)
    return prev, next
