import os
import httpx
from icecream import ic
from typing import List, Dict, Any

from infras.read_db.repos.supplier_repo import supplier_repo
from infras.read_db.repos.customer_repo import customer_repo
from infras.read_db.repos.prod_inv_repo import prod_inv_repo
from infras.read_db.repos.purchase_repo import purchase_repo
from infras.read_db.repos.sales_repo import sales_repo
from infras.read_db.repos.stockmovadj_repo import stockmovadj_repo

from schemas.v1.supplier_schemas.request_schemas import SupplierAnalyticsSchema, SupplierAnalyticsDatas
from schemas.v1.customer_schemas.request_schemas import CustomerAnalyticsSchema, CustomerAnalyticsDatas
from schemas.v1.prodinv_schemas.request_schemas import ProdInvAnalyticsSchema, ProdInvAnalyticsDatas
from schemas.v1.purchase_schemas.request_schemas import PurchaseAnalyticsSchema, PurchaseAnalyticsDatas
from schemas.v1.sales_schemas.request_schemas import SalesAnalyticsSchema, SalesAnalyticsDatas
from schemas.v1.stockmovadj_schemas.request_schemas import StockMovAdjAnalyticsSchema, StockMovAdjAnalyticsDatas

SUPPLIER_SERVICE_URL = os.getenv("SUPPLIER_SERVICE_URL", "http://localhost:8002")
CUSTOMER_SERVICE_URL = os.getenv("CUSTOMER_SERVICE_URL", "http://localhost:8006")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8004")
PURCHASE_SERVICE_URL = os.getenv("PURCHASE_SERVICE_URL", "http://localhost:8003")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8007")
STOCKMOVADJ_SERVICE_URL = os.getenv("STOCKMOVADJ_SERVICE_URL", "http://localhost:8005")

async def _fetch_all_pages(client: httpx.AsyncClient, base_url: str) -> tuple[list, int]:
    all_items = []
    offset = 1
    limit = 100
    while True:
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}limit={limit}&offset={offset}"
        resp = await client.get(url)
        if resp.status_code != 200:
            if offset == 1:
                return [], resp.status_code
            break
        r_json = resp.json()
        items = r_json.get("data", []) if isinstance(r_json, dict) else (r_json if isinstance(r_json, list) else [])
        if not items:
            break
        all_items.extend(items)
        if len(items) < limit:
            break
        offset += 1
    return all_items, 200

def _extract_customer_cleared_amount(hist: dict) -> float:
    if not isinstance(hist, dict):
        return 0.0
    payment_infos = hist.get("payment_infos") or []
    if isinstance(payment_infos, list) and payment_infos:
        p_sum = sum(float(p.get("amount") or 0.0) for p in payment_infos if isinstance(p, dict))
        if p_sum > 0:
            return p_sum
    cleared_info = hist.get("cleared_infos") or {}
    if isinstance(cleared_info, dict):
        before = float(cleared_info.get("outstanding_before") or 0.0)
        after = float(cleared_info.get("outstanding_after") or 0.0)
        if before > after:
            return before - after
        if cleared_info.get("amount"):
            return float(cleared_info.get("amount") or 0.0)
    return float(hist.get("cleared_amount") or hist.get("amount") or 0.0)

def _extract_supplier_cleared_amount(hist: dict) -> float:
    if not isinstance(hist, dict):
        return 0.0
    if hist.get("cleared_amount") is not None:
        return float(hist.get("cleared_amount") or 0.0)
    payment_infos = hist.get("payment_infos") or []
    if isinstance(payment_infos, list) and payment_infos:
        p_sum = sum(float(p.get("amount") or 0.0) for p in payment_infos if isinstance(p, dict))
        if p_sum > 0:
            return p_sum
    return float(hist.get("amount") or 0.0)

def _extract_product_analytics_items(p: dict) -> List[ProdInvAnalyticsDatas]:
    items = []
    if not isinstance(p, dict) or not p.get("id"):
        return items

    prod_id = p["id"]
    is_active = bool(p.get("is_active", True))
    created_at = str(p.get("created_at") or "")
    type_infos = p.get("type_infos") or {}
    has_batch = bool(type_infos.get("has_batch"))
    has_variant = bool(type_infos.get("has_variant"))

    if not has_variant:
        if not has_batch:
            stock_info = p.get("stock_infos") or {}
            rop_info = p.get("reorder_point_infos") or {}
            stocks = float(stock_info.get("available_stocks") or stock_info.get("physical_stocks") or 0.0)
            rop = float(rop_info.get("reorder_point") or 0.0)
            items.append(ProdInvAnalyticsDatas(
                product_id=prod_id,
                variant_id=None,
                batch_id=None,
                is_active=is_active,
                stocks=stocks,
                low_stocks=1.0 if stocks <= rop else 0.0,
                no_stocks=1.0 if stocks <= 0.0 else 0.0,
                created_at=created_at
            ))
        else:
            batch_list = p.get("batch_infos") or []
            for b in batch_list:
                if isinstance(b, dict) and b.get("id"):
                    b_stock = b.get("stock_infos") or {}
                    b_rop = b.get("reorder_point_infos") or {}
                    stocks = float(b_stock.get("available_stocks") or b_stock.get("physical_stocks") or 0.0)
                    rop = float(b_rop.get("reorder_point") or 0.0)
                    items.append(ProdInvAnalyticsDatas(
                        product_id=prod_id,
                        variant_id=None,
                        batch_id=b["id"],
                        is_active=is_active,
                        stocks=stocks,
                        low_stocks=1.0 if stocks <= rop else 0.0,
                        no_stocks=1.0 if stocks <= 0.0 else 0.0,
                        created_at=created_at
                    ))
    else:
        variants_raw = p.get("variants") or {}
        var_list = list(variants_raw.values()) if isinstance(variants_raw, dict) else (variants_raw if isinstance(variants_raw, list) else [])
        for v in var_list:
            if not isinstance(v, dict) or not v.get("id"):
                continue
            v_id = v["id"]
            if not has_batch:
                v_stock = v.get("stock_infos") or {}
                v_rop = v.get("reorder_point_infos") or {}
                stocks = float(v_stock.get("available_stocks") or v_stock.get("physical_stocks") or 0.0)
                rop = float(v_rop.get("reorder_point") or 0.0)
                items.append(ProdInvAnalyticsDatas(
                    product_id=prod_id,
                    variant_id=v_id,
                    batch_id=None,
                    is_active=is_active,
                    stocks=stocks,
                    low_stocks=1.0 if stocks <= rop else 0.0,
                    no_stocks=1.0 if stocks <= 0.0 else 0.0,
                    created_at=created_at
                ))
            else:
                v_batches = v.get("batch_infos") or []
                for b in v_batches:
                    if isinstance(b, dict) and b.get("id"):
                        b_stock = b.get("stock_infos") or {}
                        b_rop = b.get("reorder_point_infos") or {}
                        stocks = float(b_stock.get("available_stocks") or b_stock.get("physical_stocks") or 0.0)
                        rop = float(b_rop.get("reorder_point") or 0.0)
                        items.append(ProdInvAnalyticsDatas(
                            product_id=prod_id,
                            variant_id=v_id,
                            batch_id=b["id"],
                            is_active=is_active,
                            stocks=stocks,
                            low_stocks=1.0 if stocks <= rop else 0.0,
                            no_stocks=1.0 if stocks <= 0.0 else 0.0,
                            created_at=created_at
                        ))
    return items

class SyncService:
    @staticmethod
    async def sync_shop_data(shop_id: str) -> Dict[str, Any]:
        ic(f"Starting analytics synchronization for shop: {shop_id}")
        
        # 1. Clear existing analytics database records for this shop to prevent duplicate increments
        await supplier_repo.delete_shop(shop_id)
        await customer_repo.delete_shop(shop_id)
        await prod_inv_repo.delete_shop(shop_id)
        await purchase_repo.delete_shop(shop_id)
        await sales_repo.delete_shop(shop_id)
        await stockmovadj_repo.delete_shop(shop_id)
        
        status = {}
        
        # 2. Fetch and sync Suppliers
        try:
            async with httpx.AsyncClient() as client:
                suppliers, status_code = await _fetch_all_pages(client, f"{SUPPLIER_SERVICE_URL}/suppliers/by/shop/{shop_id}")
                if status_code == 200:
                    datas = []
                    for s in suppliers:
                        outstanding = s.get("outstanding_infos") or {}
                        supp_cleared = 0.0
                        try:
                            clr_hist, clr_st = await _fetch_all_pages(client, f"{SUPPLIER_SERVICE_URL}/suppliers/cleared-history/{shop_id}/{s['id']}")
                            if clr_st == 200 and clr_hist:
                                supp_cleared = sum(_extract_supplier_cleared_amount(h) for h in clr_hist)
                        except Exception:
                            pass

                        datas.append(SupplierAnalyticsDatas(
                            supplier_id=s["id"],
                            outstanding_amounts=float(outstanding.get("amount", 0.0)),
                            cleared_amounts=supp_cleared
                        ))
                    if datas:
                        payload = SupplierAnalyticsSchema(shop_id=shop_id, action="create", datas=datas)
                        await supplier_repo.process_event(payload)
                        status["suppliers"] = f"Synced {len(datas)} suppliers"
                    else:
                        status["suppliers"] = "No suppliers found"
                else:
                    status["suppliers"] = f"Failed to fetch suppliers: {status_code}"
        except Exception as e:
            status["suppliers"] = f"Error syncing suppliers: {str(e)}"

        # 3. Fetch and sync Customers
        try:
            async with httpx.AsyncClient() as client:
                customers, status_code = await _fetch_all_pages(client, f"{CUSTOMER_SERVICE_URL}/customers/by/shop/{shop_id}")
                if status_code == 200:
                    customer_cleared_map = {}
                    try:
                        clr_histories, clr_st = await _fetch_all_pages(client, f"{CUSTOMER_SERVICE_URL}/customers/cleared-histories/by/shop/{shop_id}")
                        if clr_st == 200 and clr_histories:
                            for hist in clr_histories:
                                cid = hist.get("customer_id")
                                amt = _extract_customer_cleared_amount(hist)
                                if cid:
                                    if cid not in customer_cleared_map:
                                        customer_cleared_map[cid] = {"cleared_amounts": 0.0, "settlements": 0}
                                    customer_cleared_map[cid]["cleared_amounts"] += amt
                                    customer_cleared_map[cid]["settlements"] += 1
                    except Exception as e:
                        ic(f"Error fetching customer cleared histories: {e}")

                    datas = []
                    for c in customers:
                        outstanding = c.get("outstanding_infos") or {}
                        c_clr = customer_cleared_map.get(c["id"]) or {}
                        c_cleared_amt = c_clr.get("cleared_amounts", 0.0)
                        c_settlements = c_clr.get("settlements", 0)

                        c_credit_info = c.get("credit_infos") or {}
                        c_credit_limit = float(c_credit_info.get("limit") or c.get("credit_limit") or 0.0)

                        datas.append(CustomerAnalyticsDatas(
                            customer_id=c["id"],
                            credit_limit=c_credit_limit,
                            outstanding_amounts=float(outstanding.get("amount", 0.0)),
                            cleared_amounts=c_cleared_amt,
                            settlements=c_settlements
                        ))
                    if datas:
                        payload = CustomerAnalyticsSchema(shop_id=shop_id, action="create", datas=datas)
                        await customer_repo.process_event(payload)
                        status["customers"] = f"Synced {len(datas)} customers"
                    else:
                        status["customers"] = "No customers found"
                else:
                    status["customers"] = f"Failed to fetch customers: {status_code}"
        except Exception as e:
            status["customers"] = f"Error syncing customers: {str(e)}"

        # 4. Fetch and sync Product/Inventory
        try:
            async with httpx.AsyncClient() as client:
                products, status_code = await _fetch_all_pages(client, f"{INVENTORY_SERVICE_URL}/inventories/inventories/by/shop/{shop_id}")
                if status_code != 200:
                    products, status_code = await _fetch_all_pages(client, f"{INVENTORY_SERVICE_URL}/inventories/inventories/by/shop/{shop_id}")
                
                if status_code == 200:
                    datas = []
                    for p in products:
                        datas.extend(_extract_product_analytics_items(p))
                    if datas:
                        payload = ProdInvAnalyticsSchema(shop_id=shop_id, datas=datas)
                        await prod_inv_repo.process_inventory_sync(payload)
                        status["inventory"] = f"Synced {len(datas)} product items"
                    else:
                        status["inventory"] = "No products found"
                else:
                    status["inventory"] = f"Failed to fetch inventory: {status_code}"
        except Exception as e:
            status["inventory"] = f"Error syncing inventory: {str(e)}"

        # 5. Fetch and sync Purchases
        try:
            async with httpx.AsyncClient() as client:
                purchases, status_code = await _fetch_all_pages(client, f"{PURCHASE_SERVICE_URL}/purchases/by/shop/{shop_id}")
                if status_code == 200:
                    datas = []
                    for p in purchases:
                        p_id = p.get("id") or p.get("purchase_id") or ""
                        p_date = str(p.get("created_at") or p.get("date") or "")
                        for item in p.get("items", []):
                            stocks_info = item.get("stocks_infos") or {}
                            var_info = item.get("variant_infos") or {}
                            bat_info = item.get("batch_infos") or {}
                            supp_info = p.get("supplier") or {}
                            
                            datas.append(PurchaseAnalyticsDatas(
                                purchase_id=p_id,
                                supplier_id=p.get("supplier_id") or supp_info.get("supplier_id") or "",
                                product_id=item.get("product_id") or "",
                                variant_id=var_info.get("id") or item.get("variant_id"),
                                batch_id=bat_info.get("id") or item.get("batch_id"),
                                stocks=float(stocks_info.get("stocks") or item.get("stocks") or 0.0),
                                purchase_amounts=float(item.get("total_amount") or item.get("buy_price") or 0.0),
                                outstanding_amounts=float(p.get("outstanding_amount") or 0.0),
                                created_at=p_date
                            ))
                    if datas:
                        payload = PurchaseAnalyticsSchema(shop_id=shop_id, total_purchase=len(purchases), datas=datas)
                        await purchase_repo.process_event(payload)
                        status["purchases"] = f"Synced {len(purchases)} purchases"
                    else:
                        status["purchases"] = "No purchases found"
                else:
                    status["purchases"] = f"Failed to fetch purchases: {status_code}"
        except Exception as e:
            status["purchases"] = f"Error syncing purchases: {str(e)}"

        # 6. Fetch and sync Sales (Orders)
        try:
            async with httpx.AsyncClient() as client:
                orders, status_code = await _fetch_all_pages(client, f"{ORDER_SERVICE_URL}/orders/{shop_id}")
                if status_code == 200:
                    datas = []
                    for o in orders:
                        o_date = str(o.get("created_at") or o.get("date") or "")
                        for item in o.get("items", []):
                            qty = float(item.get("quantity") or item.get("stocks") or 0.0)
                            sell_price = float(item.get("sell_price") or item.get("price") or 0.0)
                            datas.append(SalesAnalyticsDatas(
                                sales_id=o.get("id") or "",
                                customer_id=o.get("customer_id"),
                                product_id=item.get("product_id") or "",
                                variant_id=item.get("variant_id"),
                                batch_id=item.get("batch_id"),
                                stocks=qty,
                                sales_amounts=qty * sell_price,
                                sales_type=o.get("origin") or "OFFLINE",
                                created_at=o_date
                            ))
                    if datas:
                        payload = SalesAnalyticsSchema(shop_id=shop_id, datas=datas)
                        await sales_repo.process_event(payload)
                        status["sales"] = f"Synced {len(orders)} sales"
                    else:
                        status["sales"] = "No sales found"
                else:
                    status["sales"] = f"Failed to fetch sales: {status_code}"
        except Exception as e:
            status["sales"] = f"Error syncing sales: {str(e)}"

        # 7. Fetch and sync Stock Movements / Adjustments
        try:
            async with httpx.AsyncClient() as client:
                movements, status_code = await _fetch_all_pages(client, f"{STOCKMOVADJ_SERVICE_URL}/stockmovadj/by/shop/{shop_id}")
                if status_code == 200:
                    datas = []
                    for m in movements:
                        m_date = str(m.get("created_at") or m.get("date") or "")
                        for item in m.get("products", []):
                            stock_info = item.get("stock_infos") or {}
                            var_info = item.get("variant_infos") or {}
                            bat_info = item.get("batch_infos") or {}
                            
                            datas.append(StockMovAdjAnalyticsDatas(
                                product_id=item.get("product_id") or "",
                                variant_id=var_info.get("variant_id") or item.get("variant_id"),
                                batch_id=bat_info.get("batch_id") or item.get("batch_id"),
                                stocks=float(stock_info.get("stocks") or item.get("stocks") or 0.0),
                                type=item.get("type") or m.get("movement_type") or "INCREMENT",
                                created_at=m_date
                            ))
                    if datas:
                        payload = StockMovAdjAnalyticsSchema(shop_id=shop_id, datas=datas)
                        await stockmovadj_repo.process_event(payload)
                        status["stock_adjustments"] = f"Synced {len(movements)} adjustments"
                    else:
                        status["stock_adjustments"] = "No adjustments found"
                else:
                    status["stock_adjustments"] = f"Failed to fetch adjustments: {status_code}"
        except Exception as e:
            status["stock_adjustments"] = f"Error syncing adjustments: {str(e)}"

        ic(status)
        return status

    @staticmethod
    async def sync_single_supplier(shop_id: str, supplier_id: str):
        ic(f"Syncing single supplier: {supplier_id} for shop: {shop_id}")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SUPPLIER_SERVICE_URL}/suppliers/by/{shop_id}/{supplier_id}")
            s = None
            if resp.status_code == 200:
                r_data = resp.json()
                s = r_data.get("data") if isinstance(r_data, dict) and "data" in r_data else r_data
            if not s or not isinstance(s, dict):
                suppliers, _ = await _fetch_all_pages(client, f"{SUPPLIER_SERVICE_URL}/suppliers/by/shop/{shop_id}")
                s = next((item for item in suppliers if item.get("id") == supplier_id), None)
            if s:
                outstanding = s.get("outstanding_infos") or {}
                supp_cleared = 0.0
                try:
                    clr_hist, clr_st = await _fetch_all_pages(client, f"{SUPPLIER_SERVICE_URL}/suppliers/cleared-history/{shop_id}/{supplier_id}")
                    if clr_st == 200 and clr_hist:
                        supp_cleared = sum(_extract_supplier_cleared_amount(h) for h in clr_hist)
                except Exception:
                    pass
                payload = SupplierAnalyticsSchema(
                    shop_id=shop_id,
                    action="create",
                    datas=[
                        SupplierAnalyticsDatas(
                            supplier_id=s["id"],
                            outstanding_amounts=float(outstanding.get("amount", 0.0)),
                            cleared_amounts=supp_cleared,
                            created_at=str(s.get("created_at") or "")
                        )
                    ]
                )
                res = await supplier_repo.process_event(payload)
                return res or {"status": "success"}
            return {"status": "processed"}

    @staticmethod
    async def sync_single_customer(shop_id: str, customer_id: str):
        ic(f"Syncing single customer: {customer_id} for shop: {shop_id}")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{CUSTOMER_SERVICE_URL}/customers/by/id/{shop_id}/{customer_id}")
            c = None
            if resp.status_code == 200:
                r_data = resp.json()
                c = r_data.get("data") if isinstance(r_data, dict) and "data" in r_data else r_data
            if not c or not isinstance(c, dict):
                customers, _ = await _fetch_all_pages(client, f"{CUSTOMER_SERVICE_URL}/customers/by/shop/{shop_id}")
                c = next((item for item in customers if item.get("id") == customer_id), None)
            if c:
                outstanding = c.get("outstanding_infos") or {}
                c_cleared_amt = 0.0
                c_settlements = 0
                try:
                    clr_resp = await client.get(f"{CUSTOMER_SERVICE_URL}/customers/cleared-histories/by/id/{shop_id}/{customer_id}")
                    if clr_resp.status_code == 200:
                        clr_data = clr_resp.json()
                        clr_items = clr_data.get("data", []) if isinstance(clr_data, dict) else (clr_data if isinstance(clr_data, list) else [])
                        for hist in clr_items:
                            amt = _extract_customer_cleared_amount(hist)
                            c_cleared_amt += amt
                            c_settlements += 1
                    else:
                        clr_histories, clr_st = await _fetch_all_pages(client, f"{CUSTOMER_SERVICE_URL}/customers/cleared-histories/by/shop/{shop_id}")
                        if clr_st == 200 and clr_histories:
                            for hist in clr_histories:
                                if hist.get("customer_id") == customer_id:
                                    amt = _extract_customer_cleared_amount(hist)
                                    c_cleared_amt += amt
                                    c_settlements += 1
                except Exception as e:
                    ic(f"Error fetching customer cleared histories: {e}")
                c_credit_info = c.get("credit_infos") or {}
                c_credit_limit = float(c_credit_info.get("limit") or c.get("credit_limit") or 0.0)
                payload = CustomerAnalyticsSchema(
                    shop_id=shop_id,
                    action="create",
                    datas=[
                        CustomerAnalyticsDatas(
                            customer_id=c["id"],
                            credit_limit=c_credit_limit,
                            outstanding_amounts=float(outstanding.get("amount", 0.0)),
                            cleared_amounts=c_cleared_amt,
                            settlements=c_settlements,
                            created_at=str(c.get("created_at") or "")
                        )
                    ]
                )
                res = await customer_repo.process_event(payload)
                return res or {"status": "success"}
            return {"status": "processed"}

    @staticmethod
    async def sync_single_product(shop_id: str, product_id: str):
        ic(f"Syncing single product: {product_id} for shop: {shop_id}")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{INVENTORY_SERVICE_URL}/inventories/inventories/by/id/{shop_id}/{product_id}")
            p = None
            if resp.status_code == 200:
                r_data = resp.json()
                p = r_data.get("data") if isinstance(r_data, dict) and "data" in r_data else r_data
            if not p or not isinstance(p, dict):
                products, _ = await _fetch_all_pages(client, f"{INVENTORY_SERVICE_URL}/inventories/inventories/by/shop/{shop_id}")
                p = next((item for item in products if item.get("id") == product_id), None)
            if p:
                datas = _extract_product_analytics_items(p)
                if datas:
                    payload = ProdInvAnalyticsSchema(shop_id=shop_id, datas=datas)
                    res = await prod_inv_repo.process_inventory_sync(payload)
                    return res or {"status": "success"}
            return {"status": "processed"}

    @staticmethod
    async def sync_single_purchase(shop_id: str, purchase_id: str):
        ic(f"Syncing single purchase: {purchase_id} for shop: {shop_id}")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{PURCHASE_SERVICE_URL}/purchases/by/id/{shop_id}/{purchase_id}")
            p = None
            if resp.status_code == 200:
                r_data = resp.json()
                p = r_data.get("data") if isinstance(r_data, dict) and "data" in r_data else r_data
            if not p or not isinstance(p, dict):
                purchases, st = await _fetch_all_pages(client, f"{PURCHASE_SERVICE_URL}/purchases/by/shop/{shop_id}")
                if st == 200:
                    p = next((item for item in purchases if item.get("id") == purchase_id or item.get("purchase_id") == purchase_id), None)
            if p:
                p_id = p.get("id") or p.get("purchase_id") or ""
                p_date = str(p.get("created_at") or p.get("date") or "")
                datas = []
                for item in p.get("items", []):
                    stocks_info = item.get("stocks_infos") or {}
                    var_info = item.get("variant_infos") or {}
                    bat_info = item.get("batch_infos") or {}
                    supp_info = p.get("supplier") or {}
                    datas.append(PurchaseAnalyticsDatas(
                        purchase_id=p_id,
                        supplier_id=p.get("supplier_id") or supp_info.get("supplier_id") or "",
                        product_id=item.get("product_id") or "",
                        variant_id=var_info.get("id") or item.get("variant_id"),
                        batch_id=bat_info.get("id") or item.get("batch_id"),
                        stocks=float(stocks_info.get("stocks") or item.get("stocks") or 0.0),
                        purchase_amounts=float(item.get("total_amount") or item.get("buy_price") or 0.0),
                        outstanding_amounts=float(p.get("outstanding_amount") or 0.0),
                        created_at=p_date
                    ))
                if datas:
                    payload = PurchaseAnalyticsSchema(shop_id=shop_id, total_purchase=1, datas=datas)
                    res = await purchase_repo.process_event(payload)
                    return res or {"status": "success"}
            return {"status": "processed"}

    @staticmethod
    async def sync_single_order(shop_id: str, order_id: str):
        ic(f"Syncing single order: {order_id} for shop: {shop_id}")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{ORDER_SERVICE_URL}/orders/{shop_id}/{order_id}")
            o = None
            if resp.status_code == 200:
                r_data = resp.json()
                o = r_data.get("data") if isinstance(r_data, dict) and "data" in r_data else r_data
            if not o or not isinstance(o, dict):
                orders, status_code = await _fetch_all_pages(client, f"{ORDER_SERVICE_URL}/orders/{shop_id}")
                if status_code == 200 and orders:
                    o = next((item for item in orders if item.get("id") == order_id), None)
            if o:
                o_date = str(o.get("created_at") or o.get("date") or "")
                datas = []
                for item in o.get("items", []):
                    qty = float(item.get("quantity") or item.get("stocks") or 0.0)
                    sell_price = float(item.get("sell_price") or item.get("price") or 0.0)
                    datas.append(SalesAnalyticsDatas(
                        sales_id=o.get("id") or "",
                        customer_id=o.get("customer_id"),
                        product_id=item.get("product_id") or "",
                        variant_id=item.get("variant_id"),
                        batch_id=item.get("batch_id"),
                        stocks=qty,
                        sales_amounts=qty * sell_price,
                        sales_type=o.get("origin") or "OFFLINE",
                        created_at=o_date
                    ))
                if datas:
                    payload = SalesAnalyticsSchema(shop_id=shop_id, datas=datas)
                    res = await sales_repo.process_event(payload)
                    return res or {"status": "success"}
            return {"status": "processed"}

    @staticmethod
    async def sync_single_stockmovadj(shop_id: str, stockmovadj_id: str):
        ic(f"Syncing single stockmovadj: {stockmovadj_id} for shop: {shop_id}")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{STOCKMOVADJ_SERVICE_URL}/stockmovadj/by/id/{shop_id}/{stockmovadj_id}")
            m = None
            if resp.status_code == 200:
                r_data = resp.json()
                m = r_data.get("data") if isinstance(r_data, dict) and "data" in r_data else r_data
            if not m or not isinstance(m, dict):
                movements, status_code = await _fetch_all_pages(client, f"{STOCKMOVADJ_SERVICE_URL}/stockmovadj/by/shop/{shop_id}")
                if status_code == 200 and movements:
                    m = next((item for item in movements if item.get("id") == stockmovadj_id), None)
            if m:
                m_date = str(m.get("created_at") or m.get("date") or "")
                datas = []
                for item in m.get("products", []):
                    stock_info = item.get("stock_infos") or {}
                    var_info = item.get("variant_infos") or {}
                    bat_info = item.get("batch_infos") or {}
                    datas.append(StockMovAdjAnalyticsDatas(
                        product_id=item.get("product_id") or "",
                        variant_id=var_info.get("variant_id") or item.get("variant_id"),
                        batch_id=bat_info.get("batch_id") or item.get("batch_id"),
                        stocks=float(stock_info.get("stocks") or item.get("stocks") or 0.0),
                        type=item.get("type") or m.get("movement_type") or "INCREMENT",
                        created_at=m_date
                    ))
                if datas:
                    payload = StockMovAdjAnalyticsSchema(shop_id=shop_id, datas=datas)
                    res = await stockmovadj_repo.process_event(payload)
                    return res or {"status": "success"}
            return {"status": "processed"}
