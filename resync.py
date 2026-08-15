import asyncio
import os
import sys

# Add the base directory to sys.path so hyperlocal_platform can be resolved
sys.path.append(r"d:\Projects\Hyperlocal-Inventory\Apis")

from icecream import ic
from infras.read_db.repos.sync_service import SyncService

async def main():
    shop_id = "e74ade9c-7f46-5d7f-b8bf-60e99ff34687"
    ic("Starting sync for shop:", shop_id)
    await SyncService.sync_shop_data(shop_id)
    ic("Done!")

if __name__ == "__main__":
    asyncio.run(main())
