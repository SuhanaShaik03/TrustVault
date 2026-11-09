import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateDocumentStorage(FileSystemStorage):
    def __init__(self):
        location = Path(settings.PRIVATE_MEDIA_ROOT)
        if settings.IS_RENDER:
            try:
                location.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=location):
                    pass
            except OSError as error:
                raise RuntimeError(
                    "Configured PRIVATE_MEDIA_ROOT is not writable on Render. "
                    "Attach a writable persistent disk or configure PRIVATE_MEDIA_ROOT."
                ) from error
        super().__init__(location=location)
