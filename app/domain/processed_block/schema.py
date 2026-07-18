# app/domain/processed_block/schema.py
from pydantic import BaseModel


class ProcessedBlockSchema(BaseModel):
    chain_id: int
    token: str
    block_number: int
    block_hash: str
    parent_hash: str
