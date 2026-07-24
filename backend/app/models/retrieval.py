import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base_types import uuid_pk


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_table: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    vector: Mapped[list[float]] = mapped_column(Vector(1536))  # adjust dim to your embedding model
    text_chunk: Mapped[str] = mapped_column(Text)