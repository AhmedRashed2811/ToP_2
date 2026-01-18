# ToP/decorators.py
from functools import wraps
from django.http import HttpResponse
from django.shortcuts import redirect

from .utils.viewer_permissions import (
    viewer_can_access_page,
    is_company_viewer,
)

def unauthenticated_user(view_func):
    @wraps(view_func)
    def wrapper_func(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return wrapper_func


def allowed_users(allowed_roles=None):
    """
    Supports users being in multiple groups.
    """
    allowed_roles = allowed_roles or []

    def decorator(view_func):
        @wraps(view_func)
        def wrapper_func(request, *args, **kwargs):
            user_groups = set(request.user.groups.values_list("name", flat=True))
            if user_groups.intersection(set(allowed_roles)):
                return view_func(request, *args, **kwargs)
            return HttpResponse("You are not Authorized to view this page", status=403)
        return wrapper_func
    return decorator


def viewer_page_required(page_slug: str):
    """
    If user is a CompanyViewer, enforce allowed_pages contains this page.
    Non-viewers pass through.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper_func(request, *args, **kwargs):
            if is_company_viewer(request.user) and not viewer_can_access_page(request.user, page_slug):
                return HttpResponse("You are not Authorized to view this page", status=403)
            return view_func(request, *args, **kwargs)
        return wrapper_func
    return decorator
