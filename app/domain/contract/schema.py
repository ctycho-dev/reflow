# app/domain/contract/schema.py
from app.common.schema import CamelModel
from pydantic import Field


class ProtocolOutSchema(CamelModel):
    address: str
    slug: str = Field(validation_alias="protocol_slug")
    name: str = Field(validation_alias="protocol_name")
    color: str = Field(validation_alias="protocol_color")
    label: str
