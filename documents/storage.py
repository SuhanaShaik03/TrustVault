from django.conf import settings
from django.core.files.storage import FileSystemStorage


if settings.IS_VERCEL:
    from storages.backends.s3 import S3Storage

    class PrivateDocumentStorage(S3Storage):
        pass
else:

    class PrivateDocumentStorage(FileSystemStorage):
        def __init__(self):
            super().__init__(location=settings.PRIVATE_MEDIA_ROOT)
