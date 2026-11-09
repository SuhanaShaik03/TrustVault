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


def storage_diagnostics(storage):
    location = Path(storage.location)
    mount = Path(settings.PRIVATE_MEDIA_DISK_MOUNT)
    mounted = not settings.IS_RENDER or os.path.ismount(mount)
    directory_exists = location.is_dir()
    return {
        "backend": f"{storage.__class__.__module__}.{storage.__class__.__qualname__}",
        "path": str(location),
        "mount_path": str(mount),
        "disk_mounted": mounted,
        "path_configured": _is_within(location, mount),
        "directory_exists": directory_exists,
        "directory_writable": directory_exists and os.access(location, os.W_OK),
    }


def check_private_storage():
    return PrivateDocumentStorage().check_health()


class PrivateDocumentStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=Path(settings.PRIVATE_MEDIA_ROOT))

    def check_health(self):
        location = Path(self.location)
        mount = Path(settings.PRIVATE_MEDIA_DISK_MOUNT)
        path_configured = _is_within(location, mount)
        disk_mounted = not settings.IS_RENDER or os.path.ismount(mount)
        directory_exists = location.is_dir()
        directory_writable = directory_exists and os.access(location, os.W_OK)
        write_ok = False
        read_ok = False
        delete_ok = False
        probe_path = None

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
                if probe_path is not None:
                    try:
                        probe_path.unlink(missing_ok=True)
                    except OSError:
                        logger.exception("Unable to remove private storage probe file.")

        directory_exists = location.is_dir()
        directory_writable = directory_exists and os.access(location, os.W_OK)
        return {
            "disk_mounted": disk_mounted,
            "path_configured": path_configured,
            "directory_exists": directory_exists,
            "directory_writable": directory_writable,
            "write_ok": write_ok,
            "read_ok": read_ok,
            "delete_ok": delete_ok,
            "healthy": all(
                (
                    disk_mounted,
                    path_configured,
                    directory_exists,
                    directory_writable,
                    write_ok,
                    read_ok,
                    delete_ok,
                )
            ),
        }

    def _ensure_render_disk(self):
        location = Path(self.location)
        mount = Path(settings.PRIVATE_MEDIA_DISK_MOUNT)
        if not _is_within(location, mount):
            raise RuntimeError(
                "PRIVATE_MEDIA_ROOT must be inside the configured persistent disk mount."
            )
        if not os.path.ismount(mount):
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
