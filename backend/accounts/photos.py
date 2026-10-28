"""Profile photos: check an uploaded photo and save or remove it."""

import base64
import binascii
import re

from django.db import transaction

from .models import Avatar

# The app sends a small square photo (about 20-40 KB); this leaves plenty of room
MAX_BYTES = 300 * 1024
DATA_URL = re.compile(r'^data:image/[a-z+.-]+;base64,(?P<data>[A-Za-z0-9+/=\s]+)$')


class InvalidPhoto(ValueError):
    pass


def detect_type(data):
    """The real image type from the file's first bytes. SVG is never accepted: it can carry scripts."""
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


def decode_photo(data_url):
    """'data:image/jpeg;base64,...' -> (bytes, content type). Raises InvalidPhoto."""
    match = DATA_URL.match(data_url or '')
    if not match:
        raise InvalidPhoto('Send the photo as a data URL (data:image/...;base64,...).')
    try:
        data = base64.b64decode(re.sub(r'\s', '', match['data']), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidPhoto('The photo could not be read.') from exc
    if len(data) > MAX_BYTES:
        raise InvalidPhoto('The photo is too big. The largest allowed is 300 KB.')
    content_type = detect_type(data)
    if content_type is None:
        raise InvalidPhoto('Use a JPEG, PNG or WebP photo.')
    return data, content_type


@transaction.atomic
def set_photo(user, data, content_type):
    Avatar.objects.filter(user=user).delete()
    avatar = Avatar.objects.create(user=user, image=data, content_type=content_type)
    user.avatar_key = avatar.key
    user.save(update_fields=['avatar_key'])


@transaction.atomic
def remove_photo(user):
    Avatar.objects.filter(user=user).delete()
    user.avatar_key = None
    user.save(update_fields=['avatar_key'])
