import logging
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


logger = logging.getLogger(__name__)


def _is_within(path, directory):
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _render_disk_is_mounted():
    return os.path.ismount(settings.PRIVATE_MEDIA_DISK_MOUNT)


def check_private_storage():
    return PrivateDocumentStorage().check_health()


class PrivateDocumentStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=Path(settings.PRIVATE_MEDIA_ROOT))

    def check_health(self):
        location = Path(self.location)
        mount = Path(settings.PRIVATE_MEDIA_DISK_MOUNT)
        path_configured = _is_within(location, mount)
        disk_mounted = not settings.IS_RENDER or _render_disk_is_mounted()
        directory_exists = location.is_dir()
        write_ok = False
        read_ok = False
        delete_ok = False

        if disk_mounted and path_configured:
            try:
                location.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=location, delete=False) as probe:
                    probe_path = Path(probe.name)
                    probe.write(b"trustvault-private-storage-health")
                    probe.flush()
                    os.fsync(probe.fileno())
                write_ok = True
                with probe_path.open("rb") as probe:
                    read_ok = probe.read() == b"trustvault-private-storage-health"
                probe_path.unlink()
                delete_ok = True
            except OSError:
                logger.exception("Private document storage health probe failed.")
                if "probe_path" in locals():
                    try:
                        probe_path.unlink(missing_ok=True)
                    except OSError:
                        pass

        directory_exists = location.is_dir()
        return {
            "disk_mounted": disk_mounted,
            "path_configured": path_configured,
            "directory_exists": directory_exists,
            "write_ok": write_ok,
            "read_ok": read_ok,
            "delete_ok": delete_ok,
            "healthy": all(
                (disk_mounted, directory_exists, write_ok, read_ok, delete_ok)
            ) and path_configured,
        }

    def _ensure_render_disk(self):
        location = Path(self.location)
        mount = Path(settings.PRIVATE_MEDIA_DISK_MOUNT)
        if not _is_within(location, mount):
            raise RuntimeError(
                "PRIVATE_MEDIA_ROOT must be inside the configured persistent disk mount."
            )
        if not _render_disk_is_mounted():
            raise RuntimeError("The configured Render persistent disk is not mounted.")
        try:
            location.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise RuntimeError(
                "The configured Render private storage directory is not writable."
            ) from error

    def _save(self, name, content):
        if settings.IS_RENDER:
            self._ensure_render_disk()
        return super()._save(name, content)
