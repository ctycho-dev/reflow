from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chat.repository import ChatRepo
from app.domain.message.repository import MessageRepo
from app.domain.chat.schema import ChatCreateSchema, ChatUpdateSchema, ChatOutSchema
from app.domain.message.schema import MessageOutSchema

from app.domain.user.schema import UserOutSchema
from app.enums.enums import RAGType
from app.core.logger import get_logger

logger = get_logger(__name__)


class ChatService:
    def __init__(self, repo: ChatRepo, message_repo: MessageRepo):
        self.repo = repo
        self.message_repo = message_repo

    async def get_by_id(
        self, session: AsyncSession, chat_id: int, current_user: UserOutSchema
    ) -> ChatOutSchema:
        chat = await self.repo.get_by_id(session, chat_id)
        if chat.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return ChatOutSchema.model_validate(chat, from_attributes=True)

    async def list_for_user(
        self, session: AsyncSession, user_id: int, limit: int, offset: int
    ) -> list[ChatOutSchema]:
        items = await self.repo.list_for_user(session, user_id=user_id, limit=limit, offset=offset)
        return [ChatOutSchema.model_validate(c, from_attributes=True) for c in items]

    async def create(
        self, session: AsyncSession, data: ChatCreateSchema, current_user: UserOutSchema
    ) -> ChatOutSchema:
        data.user_id = current_user.id
        chat = await self.repo.create(session, data)
        await session.commit()
        await session.refresh(chat)
        return ChatOutSchema.model_validate(chat, from_attributes=True)

    async def update(
        self, session: AsyncSession, chat_id: int, data: ChatUpdateSchema, current_user: UserOutSchema
    ) -> ChatOutSchema:
        chat = await self.repo.get_by_id(session, chat_id)  # raises NotFoundError if missing
        if chat.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        updated = await self.repo.update_instance(session, chat, data, current_user_id=current_user.id)
        await session.commit()
        await session.refresh(updated)
        return ChatOutSchema.model_validate(updated, from_attributes=True)

    async def delete_by_id(
        self, session: AsyncSession, chat_id: int, current_user: UserOutSchema
    ) -> None:
        chat = await self.repo.get_by_id(session, chat_id)
        if chat.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        await session.delete(chat)
        await session.flush()
        await session.commit()

    async def find_by_external(
        self,
        session: AsyncSession,
        user_id: int,
        rag_type: RAGType,
        external_id: str,
    ) -> ChatOutSchema | None:
        chat = await self.repo.find_by_external(session, user_id, rag_type, external_id)
        return ChatOutSchema.model_validate(chat, from_attributes=True) if chat else None

    async def find_by_user_and_rag_type(
        self,
        session: AsyncSession,
        user_id: int,
        rag_type: RAGType,
    ) -> ChatOutSchema | None:
        chat = await self.repo.find_by_user_and_rag_type(session, user_id, rag_type)
        return ChatOutSchema.model_validate(chat, from_attributes=True) if chat else None
