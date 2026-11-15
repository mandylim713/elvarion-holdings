"""Database-backed file storage.

Render's disk is wiped on every deploy and the app does not serve /media/ in production, so uploaded
deposit receipts, KYC documents and avatars are kept in the database and served through a permission-checked view.
"""
import mimetypes
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    def _model(self):
        from core.models import StoredFile
        return StoredFile

    def _open(self, name, mode='rb'):
        obj = self._model().objects.get(name=name)
        return ContentFile(bytes(obj.data), name=name)

    def _save(self, name, content):
        data = content.read()
        self._model().objects.update_or_create(
            name=name,
            defaults={'data': data, 'content_type': mimetypes.guess_type(name)[0] or 'application/octet-stream'})
        return name

    def get_available_name(self, name, max_length=None):
        # Always return a fresh unique name (never overwrite another upload).
        from django.utils.crypto import get_random_string
        base, dot, ext = name.rpartition('.')
        while self.exists(name):
            name = f"{base}_{get_random_string(7)}{dot}{ext}" if dot else f"{name}_{get_random_string(7)}"
        return name[:max_length] if max_length else name

    def exists(self, name):
        return self._model().objects.filter(name=name).exists()

    def delete(self, name):
        self._model().objects.filter(name=name).delete()

    def size(self, name):
        return len(self._model().objects.get(name=name).data)

    def url(self, name):
        return '/media/' + name
