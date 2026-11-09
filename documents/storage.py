import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

class PrivateDocumentStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=Path(settings.PRIVATE_MEDIA_ROOT))

    def _save(self, name, content):
        if settings.IS_RENDER:
            location = Path(self.location)
            try:
                if not location.parent.is_dir():
                    raise OSError("The persistent media disk is not mounted.")
                location.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=location):
                    pass
            except OSError as error:
                raise RuntimeError(
                    "Configured PRIVATE_MEDIA_ROOT is not writable on Render. "
                    "Attach a writable persistent disk or configure PRIVATE_MEDIA_ROOT."
                ) from error
        return super()._save(name, content)
