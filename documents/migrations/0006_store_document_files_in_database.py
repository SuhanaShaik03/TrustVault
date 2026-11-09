import os
from pathlib import Path

from django.conf import settings
from django.db import migrations, models


def _legacy_media_root():
    return Path(
        os.environ.get(
            "PRIVATE_MEDIA_ROOT",
            str(Path(settings.BASE_DIR) / "media_private"),
        )
    ).resolve()


def _legacy_file_path(root, name):
    path = (root / name).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise RuntimeError(
            "A legacy document path points outside the configured media directory."
        ) from error
    return path


def copy_legacy_files_to_database(apps, schema_editor):
    database = schema_editor.connection.alias
    stored_files = apps.get_model("documents", "StoredDocumentFile")
    document_model = apps.get_model("documents", "Document")
    change_request_model = apps.get_model("documents", "DocumentChangeRequest")
    names = set(
        document_model.objects.using(database)
        .exclude(file="")
        .values_list("file", flat=True)
    )
    names.update(
        change_request_model.objects.using(database)
        .exclude(submitted_file="")
        .values_list("submitted_file", flat=True)
    )
    root = _legacy_media_root()
    missing = []

    for name in names:
        if stored_files.objects.using(database).filter(name=name).exists():
            continue
        path = _legacy_file_path(root, name)
        if not path.is_file():
            missing.append(name)
            continue
        stored_files.objects.using(database).create(name=name, content=path.read_bytes())

    if missing:
        raise RuntimeError(
            f"Cannot migrate {len(missing)} legacy document file(s) to PostgreSQL: "
            "their files are missing from PRIVATE_MEDIA_ROOT. Restore the files or "
            "remove the stale document records before deploying this migration."
        )


def restore_legacy_files_from_database(apps, schema_editor):
    database = schema_editor.connection.alias
    stored_files = apps.get_model("documents", "StoredDocumentFile")
    root = _legacy_media_root()

    for stored_file in stored_files.objects.using(database).iterator():
        path = _legacy_file_path(root, stored_file.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(stored_file.content))


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0005_documentchangerequest_uploaded_filename"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoredDocumentFile",
            fields=[
                (
                    "name",
                    models.CharField(max_length=255, primary_key=True, serialize=False),
                ),
                ("content", models.BinaryField()),
            ],
        ),
        migrations.RunPython(
            copy_legacy_files_to_database,
            restore_legacy_files_from_database,
        ),
    ]
