from datetime import datetime
from app.common.schema import CamelModel
from pydantic import BaseModel, ConfigDict
from app.enums.enums import RAGType


class ChatBaseSchema(BaseModel):
    rag_type: RAGType = RAGType.CLASSIC
    external_id: str | None = None


class ChatCreateSchema(CamelModel):
    rag_type: RAGType = RAGType.CLASSIC
    external_id: str | None = None


class ChatUpdateSchema(CamelModel):
    rag_type: RAGType | None = None
    external_id: str | None = None


class ChatOutSchema(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    rag_type: RAGType = RAGType.CLASSIC
    external_id: str | None = None
    created_at: datetime
    updated_at: datetime
