import asyncio
import datetime
from icecream import ic
from sqlalchemy import select
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.models.inventory_model import InventoryReservation
from infras.primary_db.repos.inventory_repo import InventoryRepo
from schemas.v1.inventory_schemas.request_schemas import ReleaseInventorySchema

async def cleanup_expired_reservations():
    """Background task to periodically release expired inventory reservations."""
    while True:
        try:
            ic("Running expired reservation cleanup job...")
            async with AsyncInventoryLocalSession() as session:
                # Find distinct session_ids with expired ACTIVE reservations
                stmt = select(InventoryReservation.session_id).where(
                    InventoryReservation.status == "ACTIVE",
                    InventoryReservation.expires_at < datetime.datetime.now(datetime.timezone.utc)
                ).distinct()
                
                result = await session.execute(stmt)
                expired_sessions = result.scalars().all()
                
                if expired_sessions:
                    ic(f"Found {len(expired_sessions)} expired sessions. Releasing reservations...")
                    repo = InventoryRepo(session=session)
                    for session_id in expired_sessions:
                        await repo.release_reservations(data=ReleaseInventorySchema(session_id=session_id))
                        ic(f"Released reservations for session: {session_id}")
                    
        except Exception as e:
            ic(f"Error in cleanup_expired_reservations: {e}")
            
        # Run every 60 seconds
        await asyncio.sleep(60)
