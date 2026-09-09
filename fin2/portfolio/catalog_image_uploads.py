"""Validate and store private catalog uploads alongside imported images."""
import fcntl
import hashlib
from io import BytesIO
import json
from pathlib import Path
import warnings
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 5_000_000
MAX_PIXELS = 20_000_000
MIMES = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}


def validate_upload(upload):
    if upload.size > MAX_BYTES:
        raise ValueError('A imagem deve ter no máximo 5 MB.')
    data = upload.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('A imagem deve ter no máximo 5 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                mime = MIMES.get(image.format)
                if mime is None:
                    raise ValueError('Selecione uma imagem PNG, JPEG ou WebP.')
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError('A imagem deve ter no máximo 20 milhões de pixels.')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
    except (OSError, SyntaxError, UnidentifiedImageError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Arquivo de imagem inválido ou danificado.') from None
    return data, mime


def store_image(root, image):
    data, mime = image
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()
    reference = 'upload:' + digest
    # Separate opens make flock serialize both threads and processes. Readers
    # always see a complete manifest, and old references remain valid for audit.
    with (root / '.upload.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest_path = root / 'manifest.json'
        entries = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        temporary = root / (uuid4().hex + '.tmp')
        try:
            temporary.write_bytes(data)
            temporary.replace(root / digest)
            entries[reference] = {'hash': digest, 'mime': mime}
            temporary.write_text(json.dumps(entries, ensure_ascii=False), encoding='utf-8')
            temporary.replace(manifest_path)
        finally:
            temporary.unlink(missing_ok=True)
    return reference
