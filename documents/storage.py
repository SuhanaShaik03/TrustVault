import logging
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db import DatabaseError, transaction
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)


@deconstructible
class DatabaseDocumentStorage(Storage):
    def _save(self, name, content):
        from documents.models import StoredDocumentFile

        StoredDocumentFile.objects.create(
            name=name,
            content=b"".join(content.chunks()),
        )
        return name

    def _open(self, name, mode="rb"):
        from documents.models import StoredDocumentFile

        if mode != "rb":
            raise ValueError("Database document storage supports read-only access.")
        try:
            stored_file = StoredDocumentFile.objects.only("content").get(name=name)
        except StoredDocumentFile.DoesNotExist as error:
            raise FileNotFoundError(name) from error
        return ContentFile(bytes(stored_file.content), name=name)

    def delete(self, name):
        from documents.models import StoredDocumentFile

        StoredDocumentFile.objects.filter(name=name).delete()

    def exists(self, name):
        from documents.models import StoredDocumentFile

        return StoredDocumentFile.objects.filter(name=name).exists()

    def size(self, name):
        from documents.models import StoredDocumentFile

        try:
            stored_file = StoredDocumentFile.objects.only("content").get(name=name)
        except StoredDocumentFile.DoesNotExist as error:
            raise FileNotFoundError(name) from error
        return len(stored_file.content)

    def url(self, name):
        raise ValueError("Database-stored documents are available only through authorized views.")


def check_database_file_storage():
    from documents.models import StoredDocumentFile

    probe_name = f"health-check/{uuid.uuid4().hex}"
    probe_content = b"trustvault-database-storage-health"
    status = {
        "database_connected": False,
        "write_ok": False,
        "read_ok": False,
        "delete_ok": False,
        "healthy": False,
    }

    try:
        with transaction.atomic():
            StoredDocumentFile.objects.create(name=probe_name, content=probe_content)
            status["database_connected"] = True
            status["write_ok"] = True
            stored_content = StoredDocumentFile.objects.values_list(
                "content", flat=True
            ).get(name=probe_name)
            status["read_ok"] = bytes(stored_content) == probe_content
            deleted_count, _ = StoredDocumentFile.objects.filter(name=probe_name).delete()
            status["delete_ok"] = deleted_count > 0
        status["healthy"] = all(
            status[key] for key in ("database_connected", "write_ok", "read_ok", "delete_ok")
        )
    except DatabaseError:
        logger.exception("PostgreSQL document storage health check failed.")

    return status


# Historical migrations import this storage class name.
PrivateDocumentStorage = DatabaseDocumentStorage
