"""
Document service — handles file storage and indexing orchestration.

Responsibilities:
1. Validate file type and size
2. Persist the file to local storage
3. Create the Document DB record (status=pending)
4. Dispatch background indexing task

Why separate service from router:
- Testable without HTTP layer
- Reusable from CLI/scripts
"""

import uuid
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import LuminaError
from app.core.logging import get_logger
from app.models.document import Document, DOCUMENT_STATUS_PENDING
from app.repositories.document_repo import DocumentRepository

logger = get_logger(__name__)


class FileTooLargeError(LuminaError):
    def __init__(self) -> None:
        super().__init__(
            status_code=413,
            error_code="FILE_TOO_LARGE",
            message=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB} MB",
        )


class UnsupportedFileTypeError(LuminaError):
    def __init__(self, file_type: str) -> None:
        super().__init__(
            status_code=415,
            error_code="UNSUPPORTED_FILE_TYPE",
            message=f"File type '{file_type}' is not supported",
            details={"allowed_types": settings.ALLOWED_FILE_TYPES},
        )


class DocumentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = DocumentRepository(db)

    async def upload(
        self,
        user_id: UUID,
        conversation_id: UUID,
        filename: str,
        file_type: str,
        file_bytes: bytes,
    ) -> Document:
        """
        Validate, store, and queue a document for indexing.

        Returns the Document record (status=pending).
        The Celery task runs separately and updates status to indexing → ready.
        """
        # Normalise content type — browsers sometimes omit charset suffix
        normalised_type = file_type.split(";")[0].strip()

        if len(file_bytes) > settings.max_file_size_bytes:
            raise FileTooLargeError()
        if normalised_type not in settings.ALLOWED_FILE_TYPES:
            raise UnsupportedFileTypeError(normalised_type)

        doc_id = uuid.uuid4()
        storage_path = self._save_file(user_id, doc_id, filename, file_bytes)

        doc = await self.repo.create(
            id=doc_id,
            user_id=user_id,
            conversation_id=conversation_id,
            filename=filename,
            file_type=normalised_type,
            file_size=len(file_bytes),
            storage_path=storage_path,
            status=DOCUMENT_STATUS_PENDING,
        )

        # Dispatch background indexing task
        try:
            from app.workers.tasks.document_indexing import index_document_task
            index_document_task.delay(str(doc.id))
        except Exception as e:
            logger.warning("document_service.task_dispatch_failed", doc_id=str(doc.id), error=str(e))

        logger.info(
            "document_service.uploaded",
            doc_id=str(doc.id),
            filename=filename,
            size=len(file_bytes),
        )
        return doc

    def _save_file(
        self,
        user_id: UUID,
        doc_id: uuid.UUID,
        filename: str,
        file_bytes: bytes,
    ) -> str:
        """
        Save file bytes to local storage.

        Path: LOCAL_STORAGE_PATH / {user_id} / {doc_id} / {filename}
        Returns the relative path (stored in Document.storage_path).
        """
        base = Path(settings.LOCAL_STORAGE_PATH)
        dest_dir = base / str(user_id) / str(doc_id)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Sanitise filename to prevent path traversal
        safe_name = Path(filename).name
        dest = dest_dir / safe_name
        dest.write_bytes(file_bytes)

        # Store relative path
        return str(dest.relative_to(base))

    @staticmethod
    def get_absolute_path(storage_path: str) -> Path:
        return Path(settings.LOCAL_STORAGE_PATH) / storage_path

    @staticmethod
    def delete_file(storage_path: str) -> None:
        """Remove stored file (called on document delete)."""
        try:
            path = DocumentService.get_absolute_path(storage_path)
            if path.exists():
                path.unlink()
            # Clean up parent dir if empty
            parent = path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except Exception as e:
            logger.warning("document_service.file_delete_failed", path=storage_path, error=str(e))
