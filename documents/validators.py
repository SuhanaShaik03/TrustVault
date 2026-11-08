from pathlib import Path

from django.core.exceptions import ValidationError

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
DOC_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def validate_document_file(upload):
    extension = Path(upload.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Upload a PDF, DOC, or DOCX document.")
    if upload.size > MAX_DOCUMENT_SIZE:
        raise ValidationError("Documents must be 10 MiB or smaller.")

    header = upload.read(8)
    upload.seek(0)
    if extension == ".pdf" and not header.startswith(b"%PDF-"):
        raise ValidationError("The uploaded file does not have a valid PDF signature.")
    if extension == ".docx" and not header.startswith(b"PK\x03\x04"):
        raise ValidationError("The uploaded file does not have a valid DOCX signature.")
    if extension == ".doc" and not header.startswith(DOC_SIGNATURE):
        raise ValidationError("The uploaded file does not have a valid DOC signature.")
