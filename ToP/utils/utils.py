# -----------------------------
# Helpers (Uploader Scoping)
# -----------------------------
from ToP.models import Project


def _get_uploader_company(user):
    uploader_profile = getattr(user, "uploader_profile", None)
    if uploader_profile and getattr(uploader_profile, "company_id", None):
        return uploader_profile.company
    return None

def _projects_qs_for_user(user):
    uploader_company = _get_uploader_company(user)
    if uploader_company:
        return Project.objects.filter(company=uploader_company)
    return Project.objects.all()


def _get_locked_company_for_uploader(user):
    """
    If user is an Uploader and has uploader_profile -> return its company, else None.
    """
    try:
        return user.uploader_profile.company
    except Exception:
        return None