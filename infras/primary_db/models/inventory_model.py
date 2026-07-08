from ..main import BASE
from sqlalchemy import Column,String,ForeignKey,Integer,TIMESTAMP,func,Float,BigInteger,Identity,Boolean,ARRAY,Date
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB


class InventoryStocks(BASE):
    __tablename__="inventory_stocks"
    id=Column(String,primary_key=True)
    shop_id=Column(String,nullable=False)
    product_id=Column(String,nullable=False)
    variant_id=Column(String,nullable=True)
    batch_id=Column(String,nullable=True)
    physical_stocks=Column(Float,nullable=False)
    reserved_stocks=Column(Float,nullable=True)
    available_stocks=Column(Float,nullable=False)
    additional_infos=Column(JSONB,nullable=True)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())


class InventoryStoragelocations(BASE):
    __tablename__="inventory_storage_locations"
    id=Column(String,primary_key=True)
    shop_id=Column(String,nullable=False)
    product_id=Column(String,nullable=False)
    variant_id=Column(String,nullable=True)
    batch_id=Column(String,nullable=True)
    name=Column(String,nullable=False)
    additional_infos=Column(JSONB,nullable=True)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())



class InventoryPricings(BASE):
    __tablename__="inventory_pricings"
    id=Column(String,primary_key=True)
    shop_id=Column(String,nullable=False)
    product_id=Column(String,nullable=False)
    variant_id=Column(String,nullable=True)
    batch_id=Column(String,nullable=True)
    buy_price=Column(Float,nullable=False)
    sell_price=Column(Float,nullable=False)
    additional_infos=Column(JSONB,nullable=True)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())


class InventoryReorderPoint(BASE):
    __tablename__="inventory_reorder_point"
    id=Column(String,primary_key=True)
    shop_id=Column(String,nullable=False)
    product_id=Column(String,nullable=False)
    variant_id=Column(String,nullable=True)
    batch_id=Column(String,nullable=True)
    reorder_point=Column(Float)
    additional_infos=Column(JSONB,nullable=True)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())



class InventoryReservation(BASE):
    __tablename__="inventory_reservations"
    id=Column(String,primary_key=True)
    session_id=Column(String,nullable=False,index=True)
    shop_id=Column(String,nullable=False)
    product_id=Column(String,nullable=False)
    variant_id=Column(String,nullable=True)
    batch_id=Column(String,nullable=True)
    serialno_infos=Column(ARRAY(JSONB),nullable=True)
    qty=Column(Float,nullable=False)
    status=Column(String,nullable=False) # ACTIVE, COMPLETED, RELEASED
    expires_at=Column(TIMESTAMP(timezone=True),nullable=False)
    
    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
