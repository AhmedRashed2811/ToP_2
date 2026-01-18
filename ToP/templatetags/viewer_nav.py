from django import template

from ..utils.viewer_permissions import (
    viewer_allowed_pages,
    is_company_viewer,
)

register = template.Library()


@register.simple_tag
def viewer_pages(user):
    """
    Returns a python set of allowed page slugs for the viewer.
    Non-viewers -> empty set.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return set()

    if not is_company_viewer(user):
        return set()

    return viewer_allowed_pages(user)
