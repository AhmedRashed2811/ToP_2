# ToP/middleware.py
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from datetime import timedelta

class InactiveUserLogoutMiddleware(MiddlewareMixin):
    """
    Logs out users in 'Client' or 'Controller' groups after N minutes of inactivity.
    Tracks per-session 'last_activity' and compares against INACTIVITY_TIMEOUT_MINUTES.
    """

    GROUPS_TO_ENFORCE = {'Client', 'Controller'}
    SESSION_KEY = 'last_activity'  # ISO string

    def process_request(self, request):
        # Skip if no authentication or no session available
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return

        # Enforce only for specific groups
        user_groups = set(request.user.groups.values_list('name', flat=True))
        if self.GROUPS_TO_ENFORCE.isdisjoint(user_groups):
            return

        # Optionally skip static/media/admin paths to avoid noise
        path = request.path or ''
        if path.startswith('/static/') or path.startswith('/media/'):
            return

        # Read timeout
        minutes = getattr(settings, 'INACTIVITY_TIMEOUT_MINUTES', 15)
        timeout_delta = timedelta(minutes=minutes)

        now = timezone.now()

        # Parse last activity from session
        last_iso = request.session.get(self.SESSION_KEY)
        if last_iso:
            try:
                last_dt = timezone.datetime.fromisoformat(last_iso)
                if timezone.is_naive(last_dt):
                    last_dt = timezone.make_aware(last_dt, timezone.get_current_timezone())
            except Exception:
                # If corrupted, reset to now
                last_dt = now
        else:
            last_dt = now

        # If exceeded, logout and redirect to login
        if now - last_dt > timeout_delta:
            # Clear activity first to avoid loops
            request.session.pop(self.SESSION_KEY, None)
            logout(request)
           
            return redirect('login')

        # Otherwise, update the activity timestamp (sliding window)
        request.session[self.SESSION_KEY] = now.isoformat()

        
