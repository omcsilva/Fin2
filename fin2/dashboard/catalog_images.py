"""Private, content-addressed copies of legacy catalog images."""
import hashlib
import json
import re
from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET


def manifest():
    try:
        return json.loads((settings.CATALOG_IMAGE_ROOT / 'manifest.json').read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


@require_GET
def catalog_image(request, identifier):
    if not re.fullmatch(r'[0-9a-f]{64}', identifier):
        raise Http404
    entry = next((v for v in manifest().values() if v['hash'] == identifier), None)
    if entry is None:
        raise Http404
    path = settings.CATALOG_IMAGE_ROOT / identifier
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise Http404
    if hashlib.sha256(data).hexdigest() != identifier:
        raise Http404
    from io import BytesIO
    response = FileResponse(BytesIO(data), content_type=entry['mime'])
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['X-Content-Type-Options'] = 'nosniff'
    return response
