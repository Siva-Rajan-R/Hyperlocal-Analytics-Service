from sqlalchemy import String,Column,Float,Boolean,TIMESTAMP,func,ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from ..main import BASE



class Products(BASE):
    __tablename__="products"
    id=Column(String,primary_key=True)
    ui_id=Column(String,nullable=False)
    shop_id=Column(String,nullable=False)
    barcode=Column(String)
    sku=Column(String,nullable=False)
    category_id=Column(String)
    unit_id=Column(String)
    name=Column(String)
    description=Column(String)
    type_infos=Column(JSONB)
    is_active=Column(Boolean,nullable=False)
    have_tracking=Column(Boolean,nullable=False)
    additional_infos=Column(JSONB,nullable=True)
    gst=Column(String,nullable=False)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())

    variants=relationship("ProductVariants",back_populates="products",cascade="all, delete-orphan")
    batches=relationship("ProductBatches",back_populates="products",cascade="all, delete-orphan")
    serialnos=relationship("ProductSerialNumbers",back_populates="products",cascade="all, delete-orphan")
    stocks = relationship(
        "InventoryStocks",
        primaryjoin="Products.id == foreign(InventoryStocks.product_id)",
        viewonly=True,
        lazy="selectin"
    )

    pricings = relationship(
        "InventoryPricings",
        primaryjoin="Products.id == foreign(InventoryPricings.product_id)",
        viewonly=True,
        lazy="selectin"
    )

    storage_locations = relationship(
        "InventoryStoragelocations",
        primaryjoin="Products.id == foreign(InventoryStoragelocations.product_id)",
        viewonly=True,
        lazy="selectin"
    )

    reorder_points = relationship(
        "InventoryReorderPoint",
        primaryjoin="Products.id == foreign(InventoryReorderPoint.product_id)",
        viewonly=True,
        lazy="selectin"
    )

class ProductVariants(BASE):
    __tablename__="product_variants"
    id=Column(String,primary_key=True)
    shop_id=Column(String,nullable=False)
    sku=Column(String,nullable=False)
    barcode=Column(String,nullable=True)
    product_id=Column(String,ForeignKey("products.id",ondelete="CASCADE"),nullable=False)
    name=Column(String,nullable=False)
    additional_infos=Column(JSONB,nullable=True)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())

    products=relationship("Products",back_populates="variants")

class ProductBatches(BASE):
    __tablename__="product_batches"
    id=Column(String,primary_key=True)
    shop_id=Column(String,nullable=False)
    product_id=Column(String,ForeignKey("products.id",ondelete="CASCADE"),nullable=False)
    variant_id=Column(String,nullable=True)
    name=Column(String,nullable=False)
    expiration_infos=Column(JSONB,nullable=False)
    additional_infos=Column(JSONB,nullable=True)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())

    products=relationship("Products",back_populates="batches")

class ProductSerialNumbers(BASE):
    __tablename__="product_serialnumbers"
    id=Column(String,primary_key=True)
    shop_id=Column(String,nullable=False)
    product_id=Column(String,ForeignKey("products.id",ondelete="CASCADE"),nullable=False)
    variant_id=Column(String,nullable=True)
    batch_id=Column(String,nullable=True)
    name=Column(String,nullable=False)
    status=Column(String,nullable=False)
    additional_infos=Column(JSONB,nullable=True)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())

    products=relationship("Products",back_populates="serialnos")
