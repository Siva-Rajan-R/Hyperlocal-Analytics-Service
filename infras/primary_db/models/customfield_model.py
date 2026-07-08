from ..main import BASE
from sqlalchemy import Column,String,ForeignKey,Integer,TIMESTAMP,func,Float,BigInteger,Identity,Boolean,ARRAY,Date
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB



class ProductCustomFields(BASE):
    __tablename__="product_custom_fields"
    id=Column(String,primary_key=True)
    shop_id=Column(String)
    field_name=Column(String)
    label_name=Column(String)
    type=Column(String)
    required=Column(Boolean)
    visible_online=Column(Boolean)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())


class ProductCustomFieldsValues(BASE):
    __tablename__="product_custom_fields_values"
    id=Column(String,primary_key=True)
    shop_id=Column(String)
    product_id=Column(String)
    field_id=Column(String)
    value=Column(String)

    created_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())

    
