from __future__ import annotations

from typing import Any, Dict, List, Optional
from ..main import PROCESSED_EVENTS

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ASCENDING, DESCENDING, UpdateOne
from pymongo.results import (
    BulkWriteResult,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)
from datetime import datetime


class BaseRepo:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    async def event_processed(
        self,
        event_id: str,
        event_type: str,
    ):
        return await PROCESSED_EVENTS.find_one(
            {
                "event_id": event_id,
                "event_type": event_type,
            }
        )
    
    async def mark_event_processed(
        self,
        event_id: str,
        event_type: str,
        shop_id: str,
    ):
        await PROCESSED_EVENTS.insert_one(
            {
                "event_id": event_id,
                "event_type": event_type,
                "shop_id": shop_id,
                "created_at": datetime.utcnow(),
            }
        )
    async def insert_one(self, document: Dict[str, Any]) -> InsertOneResult:
        return await self.collection.insert_one(document)

    async def insert_many(
        self,
        documents: List[Dict[str, Any]],
        ordered: bool = False,
    ) -> InsertManyResult:
        return await self.collection.insert_many(
            documents,
            ordered=ordered,
        )

    # ---------------------------------------------------------
    # READ
    # ---------------------------------------------------------

    async def find_one(
        self,
        filters: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one(filters, projection)

    async def find_by_id(
        self,
        document_id: str,
    ) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one(
            {"_id": ObjectId(document_id)}
        )

    async def exists(
        self,
        filters: Dict[str, Any],
    ) -> bool:
        doc = await self.collection.find_one(
            filters,
            {"_id": 1},
        )
        return doc is not None

    async def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        return await self.collection.count_documents(filters or {})

    async def find_many(
        self,
        filters: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, int]] = {},
        sort: Optional[List[tuple]] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> List[Dict[str, Any]]:
        projection={**projection,"_id": 0}
        cursor = self.collection.find(
            filters or {},
            projection,
        )

        if sort:
            cursor = cursor.sort(sort)

        if skip:
            cursor = cursor.skip(skip)

        if limit:
            cursor = cursor.limit(limit)

        return await cursor.to_list(length=limit or None)

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    async def update_one(
        self,
        filters: Dict[str, Any],
        update: Dict[str, Any],
        upsert: bool = False,
    ) -> UpdateResult:
        return await self.collection.update_one(
            filters,
            update,
            upsert=upsert,
        )

    async def update_many(
        self,
        filters: Dict[str, Any],
        update: Dict[str, Any],
    ) -> UpdateResult:
        return await self.collection.update_many(
            filters,
            update,
        )

    async def replace_one(
        self,
        filters: Dict[str, Any],
        document: Dict[str, Any],
        upsert: bool = False,
    ) -> UpdateResult:
        return await self.collection.replace_one(
            filters,
            document,
            upsert=upsert,
        )

    async def bulk_write(
        self,
        operations: List[UpdateOne],
        ordered: bool = False,
    ) -> BulkWriteResult:
        return await self.collection.bulk_write(
            operations,
            ordered=ordered,
        )

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    async def delete_one(
        self,
        filters: Dict[str, Any],
    ) -> DeleteResult:
        return await self.collection.delete_one(filters)

    async def delete_many(
        self,
        filters: Dict[str, Any],
    ) -> DeleteResult:
        return await self.collection.delete_many(filters)

    # ---------------------------------------------------------
    # AGGREGATION
    # ---------------------------------------------------------

    async def aggregate(
        self,
        pipeline: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(None)

    # ---------------------------------------------------------
    # DISTINCT
    # ---------------------------------------------------------

    async def distinct(
        self,
        field: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        return await self.collection.distinct(
            field,
            filters or {},
        )

    # ---------------------------------------------------------
    # PAGINATION
    # ---------------------------------------------------------

    async def paginate(
        self,
        filters: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, int]] = None,
        page: int = 1,
        page_size: int = 20,
        sort: Optional[List[tuple]] = None,
    ) -> Dict[str, Any]:

        page = max(page, 1)
        page_size = max(page_size, 1)

        total = await self.count(filters)

        items = await self.find_many(
            filters=filters,
            projection=projection,
            sort=sort,
            skip=(page - 1) * page_size,
            limit=page_size,
        )

        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
            "items": items,
        }

    # ---------------------------------------------------------
    # INDEXES
    # ---------------------------------------------------------

    async def create_index(
        self,
        keys: List[tuple],
        unique: bool = False,
    ):
        return await self.collection.create_index(
            keys,
            unique=unique,
        )

    async def create_indexes(
        self,
        indexes: List[Dict[str, Any]],
    ):
        for index in indexes:
            await self.collection.create_index(
                index["keys"],
                unique=index.get("unique", False),
                name=index.get("name"),
            )

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def asc(field: str):
        return (field, ASCENDING)

    @staticmethod
    def desc(field: str):
        return (field, DESCENDING)

    @staticmethod
    def inc(values: Dict[str, Any]) -> Dict[str, Any]:
        return {"$inc": values}

    @staticmethod
    def set(values: Dict[str, Any]) -> Dict[str, Any]:
        return {"$set": values}

    @staticmethod
    def unset(values: Dict[str, Any]) -> Dict[str, Any]:
        return {"$unset": values}

    @staticmethod
    def push(values: Dict[str, Any]) -> Dict[str, Any]:
        return {"$push": values}

    @staticmethod
    def add_to_set(values: Dict[str, Any]) -> Dict[str, Any]:
        return {"$addToSet": values}

    @staticmethod
    def pull(values: Dict[str, Any]) -> Dict[str, Any]:
        return {"$pull": values}

    @staticmethod
    def set_on_insert(values: Dict[str, Any]) -> Dict[str, Any]:
        return {"$setOnInsert": values}