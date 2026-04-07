"""Documents router — upload, list, and delete conversation documents for RAG."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_api_rate_limit
from app.core.exceptions import LuminaError
from app.db.session import get_db
from app.models.user import User
from app.repositories.document_repo import DocumentRepository
from app.schemas.common import SuccessResponse
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentNotFoundError(LuminaError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            error_code="DOCUMENT_NOT_FOUND",
            message="Document not found",
        )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    conversation_id: UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(require_api_rate_limit),
) -> DocumentResponse:
    """
    Upload a file and enqueue it for RAG indexing.

    Returns immediately with status='pending'. The client should poll
    GET /documents?conversation_id={id} until status='ready' or 'error'.
    """
    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "upload"

    svc = DocumentService(db)
    doc = await svc.upload(
        user_id=current_user.id,
        conversation_id=conversation_id,
        filename=filename,
        file_type=content_type,
        file_bytes=file_bytes,
    )
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    conversation_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """List all documents attached to a conversation."""
    repo = DocumentRepository(db)
    docs = await repo.get_conversation_documents(conversation_id, current_user.id)
    return [DocumentResponse.model_validate(d) for d in docs]


@router.delete("/{document_id}", response_model=SuccessResponse)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Delete a document and all its chunks. Also removes the stored file."""
    repo = DocumentRepository(db)
    doc = await repo.get_user_document(document_id, current_user.id)
    if not doc:
        raise DocumentNotFoundError()

    # Remove file from storage
    DocumentService.delete_file(doc.storage_path)

    # Cascade deletes chunks via FK
    await repo.delete(doc)
    return SuccessResponse(message="Document deleted")
