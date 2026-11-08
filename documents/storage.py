import logging
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


logger = logging.getLogger(__name__)


class PrivateDocumentStorage(FileSystemStorage):
    def __init__(self):
        location = Path(settings.PRIVATE_MEDIA_ROOT)
        if settings.IS_RENDER:
            try:
                location.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=location):
                    pass
            except OSError:
                location = Path(settings.BASE_DIR) / "media_private"
                try:
                    location.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(dir=location):
                        pass
                except OSError as fallback_error:
                    raise RuntimeError(
                        "Private document storage is not writable on Render. "
                        "Attach a writable persistent disk or configure PRIVATE_MEDIA_ROOT."
                    ) from fallback_error
                logger.warning(
                    "Configured PRIVATE_MEDIA_ROOT is not writable; falling back to "
                    "ephemeral application storage. Attach a persistent Render disk to "
                    "prevent uploaded documents from being lost on redeploy."
                )
        super().__init__(location=location)
