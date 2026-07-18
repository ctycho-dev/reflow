from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.stats.repo import StatsRepository
from app.domain.stats.schema import ProtocolStatSchema, TokenStatSchema
from app.core.logger import get_logger


logger = get_logger(__name__)


class StatsService:
    def __init__(self, repo: StatsRepository):
        self.repo = repo

    async def get_protocol_stats(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> list[ProtocolStatSchema]:
        rows = await self.repo.get_protocol_stats(session, chain_id)

        grouped: dict[str, dict] = {}

        for row in rows:
            protocol = row["protocol"]

            if protocol not in grouped:
                grouped[protocol] = {
                    "protocol": protocol,
                    "protocol_name": row["protocol_name"],
                    "protocol_color": row["protocol_color"], 
                    "tokens": [],
                }

            grouped[protocol]["tokens"].append(
                TokenStatSchema(
                    token=row["token"],
                    name=row["name"],
                    symbol=row["symbol"],
                    decimals=row["decimals"],
                    color=row["color"],
                    transfer_count=row["transfer_count"],
                    total_volume_raw=row["total_volume_raw"],
                )
            )

        return [
            ProtocolStatSchema(**group)
            for group in grouped.values()
        ]