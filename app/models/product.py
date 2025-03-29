from sqlalchemy import Column, String, Integer, ForeignKey
from app.core.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, ForeignKey("requests.request_id"))
    serial_number = Column(Integer)
    product_name = Column(String)
    input_image_urls = Column(String)  # Comma-separated URLs
    output_image_urls = Column(String)  # Comma-separated URLs (after processing)
