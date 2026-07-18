from collections import defaultdict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class StatsRepository:

    async def get_protocol_stats(
        self,
        session: AsyncSession,
        chain_id: int,
    ) -> list[dict]:
        stmt = text("""
            SELECT
                pc.protocol_slug    AS protocol,
                pc.protocol_name    AS protocol_name,
                pc.protocol_color   AS protocol_color,
                t.name              AS name,
                t.symbol            AS symbol,
                t.decimals          AS decimals,
                t.color             AS color,
                tr.token            AS token,
                COUNT(*)            AS transfer_count,
                SUM(tr.amount)      AS total_volume_raw
            FROM transfers tr
            JOIN protocol_contracts pc
                ON  tr.chain_id = pc.chain_id
                AND (tr.to_address = pc.address OR tr.from_address = pc.address)
            JOIN tokens t
                ON  tr.chain_id = t.chain_id
                AND tr.token    = t.address
            WHERE
                tr.chain_id       = :chain_id
                AND tr.block_timestamp >= NOW() - INTERVAL '24 hours'
            GROUP BY
                pc.protocol_slug,
                pc.protocol_name,
                pc.protocol_color,
                t.name,
                t.symbol,
                t.decimals,
                t.color,
                tr.token
            ORDER BY
                pc.protocol_slug,
                transfer_count DESC
        """)

        result = await session.execute(stmt, {"chain_id": chain_id})
        return [dict(row._mapping) for row in result.all()]
