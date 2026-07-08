
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, DESCENDING

from .base_repo import BaseRepo


class AnalyticsBaseRepo(BaseRepo):
    """
    Shared analytics repository utilities.
    """

    # ---------- Filter Builders ----------

    @staticmethod
    def build_match(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"$match": filters or {}}

    @staticmethod
    def build_project(fields: Dict[str, Any]) -> Dict[str, Any]:
        return {"$project": fields}

    @staticmethod
    def build_sort(field: str = "timestamp", ascending: bool = False):
        return {"$sort": {field: 1 if ascending else -1}}

    @staticmethod
    def build_limit(limit: int):
        return {"$limit": limit}

    @staticmethod
    def build_skip(skip: int):
        return {"$skip": skip}

    @staticmethod
    def build_unwind(field: str):
        return {"$unwind": f"${field}"}

    @staticmethod
    def build_replace_root(field: str):
        return {"$replaceRoot": {"newRoot": f"${field}"}}

    # ---------- Group Helpers ----------

    @staticmethod
    def group_stage(_id: Any, fields: Dict[str, Any]):
        stage = {"_id": _id}
        stage.update(fields)
        return {"$group": stage}

    @staticmethod
    def sum(field: str):
        return {"$sum": f"${field}"}

    async def count(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        return await self.collection.count_documents(filters or {})

    @staticmethod
    def avg(field: str):
        return {"$avg": f"${field}"}

    @staticmethod
    def first(field: str):
        return {"$first": f"${field}"}

    @staticmethod
    def last(field: str):
        return {"$last": f"${field}"}

    @staticmethod
    def max(field: str):
        return {"$max": f"${field}"}

    @staticmethod
    def min(field: str):
        return {"$min": f"${field}"}

    @staticmethod
    def push(field: str):
        return {"$push": f"${field}"}

    # ---------- Time Grouping ----------

    @staticmethod
    def _date_string(fmt: str, field: str = "timestamp"):
        return {
            "$dateToString": {
                "format": fmt,
                "date": f"${field}"
            }
        }

    @classmethod
    def group_day(cls, field="timestamp"):
        return cls._date_string("%Y-%m-%d", field)

    @classmethod
    def group_month(cls, field="timestamp"):
        return cls._date_string("%Y-%m", field)

    @classmethod
    def group_year(cls, field="timestamp"):
        return cls._date_string("%Y", field)

    @classmethod
    def group_hour(cls, field="timestamp"):
        return cls._date_string("%Y-%m-%d %H", field)

    # ---------- Trend Pipelines ----------

    def trend_pipeline(
        self,
        match: Dict[str, Any],
        group_id: Any,
        metrics: Dict[str, Any],
        ascending: bool = True,
    ):
        return [
            self.build_match(match),
            self.group_stage(group_id, metrics),
            {"$sort": {"_id": 1 if ascending else -1}},
        ]

    async def trend(
        self,
        match: Dict[str, Any],
        group_id: Any,
        metrics: Dict[str, Any],
    ):
        return await self.aggregate(
            self.trend_pipeline(match, group_id, metrics)
        )

    # ---------- Top N ----------

    async def top(
        self,
        filters: Dict[str, Any],
        sort_field: str,
        limit: int = 10,
        projection: Optional[Dict[str, int]] = None,
    ):
        pipeline = [
            self.build_match(filters),
            self.build_sort(sort_field),
            self.build_limit(limit),
        ]

        if projection:
            pipeline.append(self.build_project(projection))

        return await self.aggregate(pipeline)

    # ---------- Summary ----------

    async def summary(
        self,
        filters: Dict[str, Any],
        metrics: Dict[str, Any],
    ):
        pipeline = [
            self.build_match(filters),
            self.group_stage(None, metrics),
        ]

        result = await self.aggregate(pipeline)
        return result[0] if result else {}

    # ---------- Dashboard ----------

    async def dashboard(
        self,
        filters: Dict[str, Any],
        metrics: Dict[str, Any],
        latest_limit: int = 10,
    ):
        pipeline = [
            self.build_match(filters),
            {
                "$facet": {
                    "summary": [
                        self.group_stage(None, metrics)
                    ],
                    "latest": [
                        self.build_sort(),
                        self.build_limit(latest_limit),
                    ],
                }
            }
        ]

        result = await self.aggregate(pipeline)
        return result[0] if result else {}

    # ---------- Date Utilities ----------

    @staticmethod
    def last_7_days():
        return datetime.utcnow() - timedelta(days=7)

    @staticmethod
    def last_30_days():
        return datetime.utcnow() - timedelta(days=30)

    @staticmethod
    def this_year():
        now = datetime.utcnow()
        return datetime(now.year, 1, 1)

    # ---------- Pagination ----------

    async def paginate_query(
        self,
        filters: Dict[str, Any],
        page: int = 1,
        page_size: int = 20,
        sort_field: str = "timestamp",
    ):
        page = max(page, 1)
        page_size = max(page_size, 1)

        total = await self.count(filters)

        data = await self.find_many(
            filters=filters,
            skip=(page - 1) * page_size,
            limit=page_size,
            sort=[(sort_field, DESCENDING)],
        )

        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
            "items": data,
        }
