import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class Embedding(Base):
    """Phase 3 placeholder — semantic retrieval / RAG memory layer.

    This table is intentionally unused in Phase 1 and Phase 2. It will be
    populated when the career assistant gains a persistent, user-scoped
    memory store (design doc §6 — Retrieval-Augmented Generation). At that
    point the vector dimension (currently 1536, matching OpenAI
    text-embedding-3-small) should be verified against the chosen embedding
    model and a corresponding Alembic migration generated.

    Do NOT add queries against this table until the Phase 3 RAG service is
    implemented; the table will be empty for all existing users.
    """
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_table: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    vector: Mapped[list[float]] = mapped_column(Vector(1536))  # adjust dim to your embedding model
    text_chunk: Mapped[str] = mapped_column(Text)