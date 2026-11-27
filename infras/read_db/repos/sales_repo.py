from datetime import datetime
from typing import Optional

from ..main import ANALYTICS_COLLECTIONS

from schemas.v1.sales_schemas.request_schemas import SalesAnalyticsSchema
from .analytics_base_repo import AnalyticsBaseRepo


def _extract_date_str(val) -> str:
    if not val:
        return datetime.utcnow().strftime("%Y-%m-%d")
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return datetime.utcnow().strftime("%Y-%m-%d")


def _normalize_payment_method(val: str) -> str:
    if not val:
        return "Cash"
    u = str(val).strip().upper()
    if u in ("CASH",):
        return "Cash"
    if u in ("CARD", "DEBIT_CARD", "CREDIT_CARD", "DEBIT CARD", "CREDIT CARD", "POS"):
        return "Card"
    if u in ("UPI", "GPAY", "G-PAY", "PHONEPE", "PAYTM", "BHIM", "QR"):
        return "UPI"
    if "BANK" in u or u in ("NEFT", "RTGS", "IMPS", "NETBANKING", "NET_BANKING"):
        return "Bank Transfer"
    if "CREDIT" in u:
        return "Credit"
    return "Cash"

def _parse_datetime(val) -> datetime:
    if isinstance(val, datetime):
        return val
    if val:
        try:
            s = str(val).strip().replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except Exception:
            pass
    return datetime.utcnow()


class SalesRepo(AnalyticsBaseRepo):

    def __init__(self):
        super().__init__(ANALYTICS_COLLECTIONS["sales"]["overall"])
        self.overall = ANALYTICS_COLLECTIONS["sales"]["overall"]
        self.breakdown = ANALYTICS_COLLECTIONS["sales"]["breakdown"]
        self.daily = ANALYTICS_COLLECTIONS["sales"]["daily"]

    async def create_indexes(self):
        await self.overall.create_index([("shop_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("sales_id", 1)], unique=True)
        await self.breakdown.create_index([("shop_id", 1), ("date", 1)])
        await self.daily.create_index([("shop_id", 1), ("date", 1)], unique=True)
        await self.daily.create_index([("shop_id", 1), ("timestamp", -1)])

    async def process_event(self, payload: SalesAnalyticsSchema):
        # Group incoming line items by sales_id
        sales_map = {}
        for item in payload.datas:
            s_id = item.sales_id or "UNKNOWN"
            if s_id not in sales_map:
                sales_map[s_id] = {
                    "sales_id": s_id,
                    "customer_id": item.customer_id,
                    "sales_amounts": 0.0,
                    "gross_revenue": 0.0,
                    "refund_amount": 0.0,
                    "taxable_revenue": 0.0,
                    "cost_amounts": 0.0,
                    "base_cost": 0.0,
                    "returned_cost": 0.0,
                    "profit_amounts": 0.0,
                    "gross_profit": 0.0,
                    "sales_gst_amount": 0.0,
                    "returned_gst": 0.0,
                    "itc_amount": 0.0,
                    "transport_charges": 0.0,
                    "stocks": 0.0,
                    "is_gst_reg": bool(getattr(item, "is_gst_reg", False)),
                    "sales_type": (item.sales_type or "OFFLINE").upper(),
                    "payment_method": getattr(item, "payment_method", None) or "Cash",
                    "payments": getattr(item, "payments", None) or {},
                    "bill_amount": float(getattr(item, "bill_amount", 0.0) or 0.0),
                    "received_amount": float(getattr(item, "received_amount", 0.0) or 0.0),
                    "created_at": item.created_at,
                    "date": _extract_date_str(item.created_at)
                }

            item_sales_amt = float(item.sales_amounts or 0.0)
            item_gross_amt = float(getattr(item, "gross_revenue", 0.0) or item_sales_amt)
            item_refund_amt = float(getattr(item, "refund_amount", 0.0) or 0.0)
            item_taxable_amt = float(getattr(item, "taxable_revenue", 0.0) or item_sales_amt)
            item_cost_amt = float(getattr(item, "cost_amounts", 0.0) or 0.0)
            item_base_cost = float(getattr(item, "base_cost", 0.0) or item_cost_amt)
            item_ret_cost = float(getattr(item, "returned_cost", 0.0) or 0.0)
            item_profit_amt = float(getattr(item, "profit_amounts", 0.0) or (item_sales_amt - item_cost_amt))
            item_gross_profit = float(getattr(item, "gross_profit", 0.0) or (item_sales_amt - item_cost_amt))
            item_gst_amt = float(getattr(item, "sales_gst_amount", 0.0) or 0.0)
            item_ret_gst = float(getattr(item, "returned_gst", 0.0) or 0.0)
            item_itc_amt = float(getattr(item, "itc_amount", 0.0) or 0.0)
            item_trans = float(getattr(item, "transport_charges", 0.0) or 0.0)
            item_is_gst = bool(getattr(item, "is_gst_reg", False))

            sales_map[s_id]["sales_amounts"] += item_sales_amt
            sales_map[s_id]["gross_revenue"] += item_gross_amt
            sales_map[s_id]["refund_amount"] += item_refund_amt
            sales_map[s_id]["taxable_revenue"] += item_taxable_amt
            sales_map[s_id]["cost_amounts"] += item_cost_amt
            sales_map[s_id]["base_cost"] += item_base_cost
            sales_map[s_id]["returned_cost"] += item_ret_cost
            sales_map[s_id]["profit_amounts"] += item_profit_amt
            sales_map[s_id]["gross_profit"] += item_gross_profit
            sales_map[s_id]["sales_gst_amount"] += item_gst_amt
            sales_map[s_id]["returned_gst"] += item_ret_gst
            sales_map[s_id]["itc_amount"] += item_itc_amt
            sales_map[s_id]["transport_charges"] += item_trans
            sales_map[s_id]["stocks"] += float(item.stocks or 0.0)
            if item_is_gst:
                sales_map[s_id]["is_gst_reg"] = True
            if getattr(item, "bill_amount", None) and float(item.bill_amount) > sales_map[s_id]["bill_amount"]:
                sales_map[s_id]["bill_amount"] = float(item.bill_amount)
            if getattr(item, "received_amount", None) and float(item.received_amount) > sales_map[s_id]["received_amount"]:
                sales_map[s_id]["received_amount"] = float(item.received_amount)
            if getattr(item, "payments", None):
                sales_map[s_id]["payments"] = item.payments
            if getattr(item, "payment_method", None):
                sales_map[s_id]["payment_method"] = item.payment_method

            # Update product inventory analytics
            from .prod_inv_repo import prod_inv_repo
            await prod_inv_repo.apply_sale(
                shop_id=payload.shop_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                batch_id=item.batch_id,
                stocks=item.stocks or 0.0,
                amount=item.sales_amounts or 0.0,
                sales_type=item.sales_type,
            )

            # Update customer analytics (if customer_id is provided)
            if item.customer_id:
                from .customer_repo import customer_repo
                await customer_repo.apply_sale(
                    shop_id=payload.shop_id,
                    customer_id=item.customer_id,
                    amount=item.sales_amounts or 0.0,
                    sales_type=item.sales_type,
                )

        # Upsert each order into breakdown collection (idempotent!)
        for s_id, s_data in sales_map.items():
            if s_data["bill_amount"] <= 0.0:
                s_data["bill_amount"] = s_data["sales_amounts"]
            if s_data["received_amount"] <= 0.0 and _normalize_payment_method(s_data["payment_method"]) != "Credit":
                s_data["received_amount"] = s_data["bill_amount"]

            await self.breakdown.update_one(
                {"shop_id": payload.shop_id, "sales_id": s_id},
                {
                    "$set": {
                        "shop_id": payload.shop_id,
                        "sales_id": s_id,
                        "customer_id": s_data["customer_id"],
                        "sales_amounts": s_data["sales_amounts"],
                        "gross_revenue": s_data["gross_revenue"],
                        "refund_amount": s_data["refund_amount"],
                        "taxable_revenue": s_data["taxable_revenue"],
                        "cost_amounts": s_data["cost_amounts"],
                        "base_cost": s_data["base_cost"],
                        "returned_cost": s_data["returned_cost"],
                        "profit_amounts": s_data["profit_amounts"],
                        "gross_profit": s_data["gross_profit"],
                        "sales_gst_amount": s_data["sales_gst_amount"],
                        "returned_gst": s_data["returned_gst"],
                        "itc_amount": s_data["itc_amount"],
                        "transport_charges": s_data["transport_charges"],
                        "is_gst_reg": s_data["is_gst_reg"],
                        "stocks": s_data["stocks"],
                        "sales_type": s_data["sales_type"],
                        "payment_method": s_data["payment_method"],
                        "payments": s_data["payments"],
                        "bill_amount": s_data["bill_amount"],
                        "received_amount": s_data["received_amount"],
                        "date": s_data["date"],
                        "created_at": s_data["created_at"],
                        "timestamp": _parse_datetime(s_data["created_at"]) if s_data.get("created_at") else datetime.utcnow()
                    }
                },
                upsert=True
            )

        # Recalculate overall and daily from breakdown
        await self.recalculate_overall(payload.shop_id)
        await self.recalculate_daily(payload.shop_id)
        return {"status": "success"}

    async def recalculate_overall(self, shop_id: str):
        pipeline = [
            {"$match": {"shop_id": shop_id}},
            {
                "$group": {
                    "_id": "$shop_id",
                    "total_sales": {
                        "$sum": {
                            "$cond": [
                                {"$or": [
                                    {"$gt": ["$stocks", 0]},
                                    {"$gt": ["$sales_amounts", 0]}
                                ]},
                                1,
                                0
                            ]
                        }
                    },
                    "total_sales_amounts": {"$sum": "$sales_amounts"},
                    "gross_revenue": {"$sum": "$gross_revenue"},
                    "refund_amount": {"$sum": "$refund_amount"},
                    "taxable_revenue": {"$sum": "$taxable_revenue"},
                    "total_cost": {"$sum": "$cost_amounts"},
                    "base_cost": {"$sum": "$base_cost"},
                    "returned_cost": {"$sum": "$returned_cost"},
                    "total_profit": {"$sum": "$profit_amounts"},
                    "gross_profit": {"$sum": "$gross_profit"},
                    "sales_gst_amount": {"$sum": "$sales_gst_amount"},
                    "returned_gst": {"$sum": "$returned_gst"},
                    "itc_amount": {"$sum": "$itc_amount"},
                    "transport_charges": {"$sum": "$transport_charges"},
                    "total_sales_stocks": {"$sum": "$stocks"},
                    "total_online_sales": {
                        "$sum": {
                            "$cond": [
                                {"$and": [
                                    {"$eq": ["$sales_type", "ONLINE"]},
                                    {"$or": [
                                        {"$gt": ["$stocks", 0]},
                                        {"$gt": ["$sales_amounts", 0]}
                                    ]}
                                ]},
                                1,
                                0
                            ]
                        }
                    },
                    "total_online_sales_amount": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "total_offline_sales": {
                        "$sum": {
                            "$cond": [
                                {"$and": [
                                    {"$ne": ["$sales_type", "ONLINE"]},
                                    {"$or": [
                                        {"$gt": ["$stocks", 0]},
                                        {"$gt": ["$sales_amounts", 0]}
                                    ]}
                                ]},
                                1,
                                0
                            ]
                        }
                    },
                    "total_offline_sales_amount": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "is_gst_reg": {
                        "$max": "$is_gst_reg"
                    }
                }
            }
        ]
        agg_res = await self.breakdown.aggregate(pipeline).to_list(1)

        # Compute payment breakdown and bill/received totals
        orders = await self.breakdown.find({"shop_id": shop_id}).to_list(length=None)
        payment_breakdown = {
            "Cash": {"name": "Cash", "value": 0.0, "amount": 0.0, "count": 0, "color": "#10b981"},
            "UPI": {"name": "UPI", "value": 0.0, "amount": 0.0, "count": 0, "color": "#3b82f6"},
            "Card": {"name": "Card", "value": 0.0, "amount": 0.0, "count": 0, "color": "#6366f1"},
            "Bank Transfer": {"name": "Bank Transfer", "value": 0.0, "amount": 0.0, "count": 0, "color": "#06b6d4"},
            "Credit": {"name": "Credit", "value": 0.0, "amount": 0.0, "count": 0, "color": "#f59e0b"},
        }
        total_bill_amount = 0.0
        total_received_amount = 0.0
        for o in orders:
            # Skip fully returned / inactive sales
            if float(o.get("stocks") or 0.0) <= 0.0 and float(o.get("sales_amounts") or 0.0) <= 0.0:
                continue

            b_amt = float(o.get("bill_amount") or o.get("sales_amounts") or 0.0)
            total_bill_amount += b_amt
            r_amt = float(o.get("received_amount") or 0.0)
            if r_amt <= 0.0 and _normalize_payment_method(o.get("payment_method")) != "Credit":
                r_amt = b_amt
            total_received_amount += r_amt

            p_dict = o.get("payments")
            if isinstance(p_dict, dict) and p_dict:
                for pm, pamt in p_dict.items():
                    norm = _normalize_payment_method(pm)
                    if norm not in payment_breakdown:
                        norm = "Cash"
                    val = float(pamt or 0.0)
                    payment_breakdown[norm]["amount"] += val
                    payment_breakdown[norm]["value"] += val
                    payment_breakdown[norm]["count"] += 1
            else:
                pm = o.get("payment_method") or "Cash"
                norm = _normalize_payment_method(pm)
                if norm not in payment_breakdown:
                    norm = "Cash"
                payment_breakdown[norm]["amount"] += b_amt
                payment_breakdown[norm]["value"] += b_amt
                payment_breakdown[norm]["count"] += 1

        if agg_res:
            tot = agg_res[0]
            is_gst = bool(tot.get("is_gst_reg", False))
            net_sales = float(tot.get("total_sales_amounts", 0.0))
            taxable_rev = float(tot.get("taxable_revenue", 0.0))
            eff_cost = float(tot.get("total_cost", 0.0))
            base_c = float(tot.get("base_cost", 0.0))
            out_gst = float(tot.get("sales_gst_amount", 0.0)) if is_gst else 0.0
            in_itc = float(tot.get("itc_amount", 0.0)) if is_gst else 0.0
            trans = float(tot.get("transport_charges", 0.0))
            profit = float(tot.get("total_profit", 0.0))

            net_gst_payable = max(0.0, out_gst - in_itc) if is_gst else 0.0
            itc_surplus = max(0.0, in_itc - out_gst) if is_gst else 0.0

            denom = taxable_rev if (is_gst and taxable_rev > 0) else (net_sales if net_sales > 0 else 1.0)
            profit_margin = round((profit / denom) * 100.0, 2) if denom > 0 else 0.0
            gross_margin = round(((float(tot.get("gross_profit", 0.0))) / (net_sales or 1.0)) * 100.0, 2) if net_sales > 0 else 0.0

            await self.overall.update_one(
                {"shop_id": shop_id},
                {
                    "$set": {
                        "shop_id": shop_id,
                        "total_sales": int(tot.get("total_sales", 0)),
                        "total_sales_amounts": net_sales,
                        "gross_revenue": float(tot.get("gross_revenue", 0.0)),
                        "refund_amount": float(tot.get("refund_amount", 0.0)),
                        "taxable_revenue": taxable_rev,
                        "total_cost": eff_cost,
                        "base_cost": base_c,
                        "returned_cost": float(tot.get("returned_cost", 0.0)),
                        "total_profit": profit,
                        "gross_profit": float(tot.get("gross_profit", 0.0)),
                        "sales_gst_amount": out_gst,
                        "returned_gst": float(tot.get("returned_gst", 0.0)),
                        "itc_amount": in_itc,
                        "transport_charges": trans,
                        "net_gst_payable": net_gst_payable,
                        "itc_surplus": itc_surplus,
                        "profit_margin": profit_margin,
                        "gross_margin": gross_margin,
                        "is_gst_reg": is_gst,
                        "total_sales_stocks": float(tot.get("total_sales_stocks", 0.0)),
                        "total_online_sales": int(tot.get("total_online_sales", 0)),
                        "total_online_sales_amount": float(tot.get("total_online_sales_amount", 0.0)),
                        "total_offline_sales": int(tot.get("total_offline_sales", 0)),
                        "total_offline_sales_amount": float(tot.get("total_offline_sales_amount", 0.0)),
                        "total_bill_amount": total_bill_amount,
                        "total_received_amount": total_received_amount,
                        "payment_breakdown": list(payment_breakdown.values()),
                        "timestamp": datetime.utcnow(),
                    }
                },
                upsert=True
            )
        else:
            await self.overall.update_one(
                {"shop_id": shop_id},
                {
                    "$set": {
                        "shop_id": shop_id,
                        "total_sales": 0,
                        "total_sales_amounts": 0.0,
                        "gross_revenue": 0.0,
                        "refund_amount": 0.0,
                        "taxable_revenue": 0.0,
                        "total_cost": 0.0,
                        "base_cost": 0.0,
                        "returned_cost": 0.0,
                        "total_profit": 0.0,
                        "gross_profit": 0.0,
                        "sales_gst_amount": 0.0,
                        "returned_gst": 0.0,
                        "itc_amount": 0.0,
                        "transport_charges": 0.0,
                        "net_gst_payable": 0.0,
                        "itc_surplus": 0.0,
                        "profit_margin": 0.0,
                        "gross_margin": 0.0,
                        "is_gst_reg": False,
                        "total_sales_stocks": 0.0,
                        "total_online_sales": 0,
                        "total_online_sales_amount": 0.0,
                        "total_offline_sales": 0,
                        "total_offline_sales_amount": 0.0,
                        "total_bill_amount": 0.0,
                        "total_received_amount": 0.0,
                        "payment_breakdown": list(payment_breakdown.values()),
                        "timestamp": datetime.utcnow(),
                    }
                },
                upsert=True
            )

    async def recalculate_daily(self, shop_id: str):
        pipeline = [
            {"$match": {"shop_id": shop_id}},
            {
                "$group": {
                    "_id": "$date",
                    "total_sales": {
                        "$sum": {
                            "$cond": [
                                {"$or": [
                                    {"$gt": ["$stocks", 0]},
                                    {"$gt": ["$sales_amounts", 0]}
                                ]},
                                1,
                                0
                            ]
                        }
                    },
                    "total_sales_amounts": {"$sum": "$sales_amounts"},
                    "gross_revenue": {"$sum": "$gross_revenue"},
                    "refund_amount": {"$sum": "$refund_amount"},
                    "taxable_revenue": {"$sum": "$taxable_revenue"},
                    "total_cost": {"$sum": "$cost_amounts"},
                    "base_cost": {"$sum": "$base_cost"},
                    "returned_cost": {"$sum": "$returned_cost"},
                    "total_profit": {"$sum": "$profit_amounts"},
                    "gross_profit": {"$sum": "$gross_profit"},
                    "sales_gst_amount": {"$sum": "$sales_gst_amount"},
                    "returned_gst": {"$sum": "$returned_gst"},
                    "itc_amount": {"$sum": "$itc_amount"},
                    "transport_charges": {"$sum": "$transport_charges"},
                    "is_gst_reg": {"$max": "$is_gst_reg"},
                    "total_sales_stocks": {"$sum": "$stocks"},
                    "total_online_sales": {
                        "$sum": {
                            "$cond": [
                                {"$and": [
                                    {"$eq": ["$sales_type", "ONLINE"]},
                                    {"$or": [
                                        {"$gt": ["$stocks", 0]},
                                        {"$gt": ["$sales_amounts", 0]}
                                    ]}
                                ]},
                                1,
                                0
                            ]
                        }
                    },
                    "total_online_sales_amount": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "total_offline_sales": {
                        "$sum": {
                            "$cond": [
                                {"$and": [
                                    {"$ne": ["$sales_type", "ONLINE"]},
                                    {"$or": [
                                        {"$gt": ["$stocks", 0]},
                                        {"$gt": ["$sales_amounts", 0]}
                                    ]}
                                ]},
                                1,
                                0
                            ]
                        }
                    },
                    "total_offline_sales_amount": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "latest_timestamp": {"$max": "$timestamp"}
                }
            }
        ]
        daily_res = await self.breakdown.aggregate(pipeline).to_list(None)
        await self.daily.delete_many({"shop_id": shop_id})
        for d in daily_res:
            date_str = d["_id"] or datetime.utcnow().strftime("%Y-%m-%d")
            is_gst = bool(d.get("is_gst_reg", False))
            out_gst = float(d.get("sales_gst_amount", 0.0)) if is_gst else 0.0
            in_itc = float(d.get("itc_amount", 0.0)) if is_gst else 0.0
            await self.daily.update_one(
                {"shop_id": shop_id, "date": date_str},
                {
                    "$set": {
                        "shop_id": shop_id,
                        "date": date_str,
                        "total_sales": int(d.get("total_sales", 0)),
                        "total_sales_amounts": float(d.get("total_sales_amounts", 0.0)),
                        "gross_revenue": float(d.get("gross_revenue", 0.0)),
                        "refund_amount": float(d.get("refund_amount", 0.0)),
                        "taxable_revenue": float(d.get("taxable_revenue", 0.0)),
                        "total_cost": float(d.get("total_cost", 0.0)),
                        "base_cost": float(d.get("base_cost", 0.0)),
                        "returned_cost": float(d.get("returned_cost", 0.0)),
                        "total_profit": float(d.get("total_profit", 0.0)),
                        "gross_profit": float(d.get("gross_profit", 0.0)),
                        "sales_gst_amount": out_gst,
                        "returned_gst": float(d.get("returned_gst", 0.0)),
                        "itc_amount": in_itc,
                        "transport_charges": float(d.get("transport_charges", 0.0)),
                        "net_gst_payable": max(0.0, out_gst - in_itc) if is_gst else 0.0,
                        "itc_surplus": max(0.0, in_itc - out_gst) if is_gst else 0.0,
                        "is_gst_reg": is_gst,
                        "total_sales_stocks": float(d.get("total_sales_stocks", 0.0)),
                        "total_online_sales": int(d.get("total_online_sales", 0)),
                        "total_online_sales_amount": float(d.get("total_online_sales_amount", 0.0)),
                        "total_offline_sales": int(d.get("total_offline_sales", 0)),
                        "total_offline_sales_amount": float(d.get("total_offline_sales_amount", 0.0)),
                        "timestamp": d.get("latest_timestamp") or datetime.utcnow()
                    }
                },
                upsert=True
            )

    async def get_overall(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        if not start_date and not end_date:
            doc = await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})
            if not doc or "gross_revenue" not in doc or "taxable_revenue" not in doc:
                await self.recalculate_overall(shop_id)
                doc = await self.overall.find_one({"shop_id": shop_id}, {"_id": 0})
            return doc

        filters = {"shop_id": shop_id}
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = _extract_date_str(start_date)
            if end_date:
                date_filter["$lte"] = _extract_date_str(end_date)
            filters["date"] = date_filter

        cursor = self.breakdown.aggregate([
            {"$match": filters},
            {
                "$group": {
                    "_id": "$shop_id",
                    "total_sales": {
                        "$sum": {
                            "$cond": [
                                {"$or": [
                                    {"$gt": ["$stocks", 0]},
                                    {"$gt": ["$sales_amounts", 0]}
                                ]},
                                1,
                                0
                            ]
                        }
                    },
                    "total_sales_amounts": {"$sum": "$sales_amounts"},
                    "gross_revenue": {"$sum": "$gross_revenue"},
                    "refund_amount": {"$sum": "$refund_amount"},
                    "taxable_revenue": {"$sum": "$taxable_revenue"},
                    "total_cost": {"$sum": "$cost_amounts"},
                    "base_cost": {"$sum": "$base_cost"},
                    "returned_cost": {"$sum": "$returned_cost"},
                    "total_profit": {"$sum": "$profit_amounts"},
                    "gross_profit": {"$sum": "$gross_profit"},
                    "sales_gst_amount": {"$sum": "$sales_gst_amount"},
                    "returned_gst": {"$sum": "$returned_gst"},
                    "itc_amount": {"$sum": "$itc_amount"},
                    "transport_charges": {"$sum": "$transport_charges"},
                    "total_sales_stocks": {"$sum": "$stocks"},
                    "total_online_sales": {
                        "$sum": {
                            "$cond": [
                                {"$and": [
                                    {"$eq": ["$sales_type", "ONLINE"]},
                                    {"$or": [
                                        {"$gt": ["$stocks", 0]},
                                        {"$gt": ["$sales_amounts", 0]}
                                    ]}
                                ]},
                                1,
                                0
                            ]
                        }
                    },
                    "total_online_sales_amount": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "total_offline_sales": {
                        "$sum": {
                            "$cond": [
                                {"$and": [
                                    {"$ne": ["$sales_type", "ONLINE"]},
                                    {"$or": [
                                        {"$gt": ["$stocks", 0]},
                                        {"$gt": ["$sales_amounts", 0]}
                                    ]}
                                ]},
                                1,
                                0
                            ]
                        }
                    },
                    "total_offline_sales_amount": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "is_gst_reg": {"$max": "$is_gst_reg"}
                }
            }
        ])
        res = await cursor.to_list(1)
        if res and (float(res[0].get("total_sales_amounts", 0.0) or 0.0) > 0.0 or int(res[0].get("total_sales", 0)) > 0):
            res[0].pop("_id", None)
            res[0]["shop_id"] = shop_id
            
            is_gst = bool(res[0].get("is_gst_reg", False))
            net_sales = float(res[0].get("total_sales_amounts", 0.0))
            taxable_rev = float(res[0].get("taxable_revenue", 0.0))
            out_gst = float(res[0].get("sales_gst_amount", 0.0)) if is_gst else 0.0
            in_itc = float(res[0].get("itc_amount", 0.0)) if is_gst else 0.0
            profit = float(res[0].get("total_profit", 0.0))

            res[0]["sales_gst_amount"] = out_gst
            res[0]["itc_amount"] = in_itc
            res[0]["net_gst_payable"] = max(0.0, out_gst - in_itc) if is_gst else 0.0
            res[0]["itc_surplus"] = max(0.0, in_itc - out_gst) if is_gst else 0.0

            denom = taxable_rev if (is_gst and taxable_rev > 0) else (net_sales if net_sales > 0 else 1.0)
            res[0]["profit_margin"] = round((profit / denom) * 100.0, 2) if denom > 0 else 0.0
            res[0]["gross_margin"] = round(((float(res[0].get("gross_profit", 0.0))) / (net_sales or 1.0)) * 100.0, 2) if net_sales > 0 else 0.0

            # Compute filtered payment breakdown and totals
            filtered_orders = await self.breakdown.find(filters).to_list(length=None)
            f_payment_breakdown = {
                "Cash": {"name": "Cash", "value": 0.0, "amount": 0.0, "count": 0, "color": "#10b981"},
                "UPI": {"name": "UPI", "value": 0.0, "amount": 0.0, "count": 0, "color": "#3b82f6"},
                "Card": {"name": "Card", "value": 0.0, "amount": 0.0, "count": 0, "color": "#6366f1"},
                "Bank Transfer": {"name": "Bank Transfer", "value": 0.0, "amount": 0.0, "count": 0, "color": "#06b6d4"},
                "Credit": {"name": "Credit", "value": 0.0, "amount": 0.0, "count": 0, "color": "#f59e0b"},
            }
            f_bill = 0.0
            f_received = 0.0
            for fo in filtered_orders:
                fb = float(fo.get("bill_amount") or fo.get("sales_amounts") or 0.0)
                f_bill += fb
                fr = float(fo.get("received_amount") or 0.0)
                if fr <= 0.0 and _normalize_payment_method(fo.get("payment_method")) != "Credit":
                    fr = fb
                f_received += fr
                fp = fo.get("payments")
                if isinstance(fp, dict) and fp:
                    for pm, pamt in fp.items():
                        norm = _normalize_payment_method(pm)
                        if norm in f_payment_breakdown:
                            v = float(pamt or 0.0)
                            f_payment_breakdown[norm]["amount"] += v
                            f_payment_breakdown[norm]["value"] += v
                            f_payment_breakdown[norm]["count"] += 1
                else:
                    pm = fo.get("payment_method") or "Cash"
                    norm = _normalize_payment_method(pm)
                    if norm in f_payment_breakdown:
                        f_payment_breakdown[norm]["amount"] += fb
                        f_payment_breakdown[norm]["value"] += fb
                        f_payment_breakdown[norm]["count"] += 1
            res[0]["total_bill_amount"] = f_bill
            res[0]["total_received_amount"] = f_received
            res[0]["payment_breakdown"] = list(f_payment_breakdown.values())
            return res[0]

        # Fallback: check ProdInv for products with recorded sales (only when NO date filter is specified)
        if not start_date and not end_date:
            try:
                from .prod_inv_repo import prod_inv_repo
                top_prods = await prod_inv_repo.top_products(shop_id, limit=100) or []
                p_sales_amt = sum(float(p.get("total_sales_amounts", 0.0) or p.get("total_offline_sales_amount", 0.0) or 0.0) for p in top_prods)
                p_sales_stocks = sum(float(p.get("total_sales_stocks", 0.0) or 0.0) for p in top_prods)
                p_offline_sales = sum(int(p.get("total_offline_sales", 0) or 0) for p in top_prods)
                p_offline_amt = sum(float(p.get("total_offline_sales_amount", 0.0) or 0.0) for p in top_prods)
                p_online_sales = sum(int(p.get("total_online_sales", 0) or 0) for p in top_prods)
                p_online_amt = sum(float(p.get("total_online_sales_amount", 0.0) or 0.0) for p in top_prods)
                if p_sales_amt > 0 or p_sales_stocks > 0 or p_offline_sales > 0:
                    return {
                        "shop_id": shop_id,
                        "total_sales": max(1, p_offline_sales + p_online_sales),
                        "total_sales_amounts": p_sales_amt,
                        "total_cost": 0.0,
                        "total_profit": p_sales_amt,
                        "total_sales_stocks": p_sales_stocks,
                        "total_online_sales": p_online_sales,
                        "total_online_sales_amount": p_online_amt,
                        "total_offline_sales": p_offline_sales or max(1, int(p_sales_stocks)),
                        "total_offline_sales_amount": p_offline_amt or p_sales_amt,
                    }
            except Exception:
                pass

        return {
            "shop_id": shop_id,
            "total_sales": 0,
            "total_sales_amounts": 0.0,
            "total_cost": 0.0,
            "total_profit": 0.0,
            "total_sales_stocks": 0.0,
            "total_online_sales": 0,
            "total_online_sales_amount": 0.0,
            "total_offline_sales": 0,
            "total_offline_sales_amount": 0.0,
        }

    async def get_daily(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        filters = {"shop_id": shop_id}

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = _extract_date_str(start_date)
            if end_date:
                date_filter["$lte"] = _extract_date_str(end_date)
            filters["date"] = date_filter

        return await self.find_many(
            filters=filters,
            sort=[("date", -1)],
        )

    async def sales_trend(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        filters = {"shop_id": shop_id}
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = _extract_date_str(start_date)
            if end_date:
                date_filter["$lte"] = _extract_date_str(end_date)
            filters["date"] = date_filter

        cursor = self.breakdown.aggregate([
            {"$match": filters},
            {
                "$group": {
                    "_id": "$date",
                    "total_sales": {"$sum": 1},
                    "total_sales_amounts": {"$sum": "$sales_amounts"},
                    "total_cost": {"$sum": "$cost_amounts"},
                    "total_profit": {"$sum": "$profit_amounts"},
                    "total_sales_stocks": {"$sum": "$stocks"},
                    "total_online_sales": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_online_sales_amount": {
                        "$sum": {"$cond": [{"$eq": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                    "total_offline_sales": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, 1, 0]}
                    },
                    "total_offline_sales_amount": {
                        "$sum": {"$cond": [{"$ne": ["$sales_type", "ONLINE"]}, "$sales_amounts", 0.0]}
                    },
                }
            },
            {"$sort": {"_id": 1}},
        ])
        cursor_res = await cursor.to_list(length=None)
        if cursor_res:
            return cursor_res

        try:
            from .prod_inv_repo import prod_inv_repo
            top_prods = await prod_inv_repo.top_products(shop_id, limit=100) or []
            p_sales_amt = sum(float(p.get("total_sales_amounts", 0.0) or p.get("total_offline_sales_amount", 0.0) or 0.0) for p in top_prods)
            p_offline_cnt = sum(int(p.get("total_offline_sales", 0) or 0) for p in top_prods)
            if p_sales_amt > 0:
                d_str = datetime.utcnow().strftime("%Y-%m-%d")
                return [
                    {
                        "_id": d_str,
                        "date": d_str,
                        "total_sales": max(1, p_offline_cnt),
                        "total_sales_amounts": p_sales_amt,
                        "total_cost": 0.0,
                        "total_profit": p_sales_amt,
                        "total_sales_stocks": sum(float(p.get("total_sales_stocks", 0.0) or 0.0) for p in top_prods),
                        "total_online_sales": 0,
                        "total_online_sales_amount": 0.0,
                        "total_offline_sales": max(1, p_offline_cnt),
                        "total_offline_sales_amount": p_sales_amt,
                    }
                ]
        except Exception:
            pass

        return []

    async def dashboard(
        self,
        shop_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        return {
            "overall": await self.get_overall(shop_id, start_date, end_date),
            "trend": await self.sales_trend(shop_id, start_date, end_date),
        }

    async def delete_shop(self, shop_id: str):
        await self.overall.delete_one({"shop_id": shop_id})
        await self.breakdown.delete_many({"shop_id": shop_id})
        await self.daily.delete_many({"shop_id": shop_id})


sales_repo = SalesRepo()
