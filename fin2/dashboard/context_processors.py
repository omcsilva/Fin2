"""Small environment-specific values shared by dashboard templates."""
from django.conf import settings

def environment(request):
    return {"favicon_static_name": settings.FAVICON_STATIC_NAME,
            "fin1_base_url": settings.FIN1_BASE_URL}
