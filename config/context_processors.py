from django.conf import settings


def site(request):
    """Return a small context dict with SITE_NAME for templates."""
    return {"SITE_NAME": getattr(settings, "SITE_NAME", "alansalbums")}
