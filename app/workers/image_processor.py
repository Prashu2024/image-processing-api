import os
import requests
from PIL import Image
from io import BytesIO
import uuid
from datetime import datetime
from app.models.request import Request, RequestStatus
from app.models.product import Product
from app.core.database import SessionLocal
from app.routers.status import trigger_webhook
import time

PROCESSED_DIR = "processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Get base URL for processed images from env var, default to localhost
PROCESSED_URL_BASE = os.getenv("PROCESSED_URL_BASE", "http://localhost:8000/processed/")
# Ensure base URL ends with a slash
if not PROCESSED_URL_BASE.endswith('/'):
    PROCESSED_URL_BASE += '/'

def process_images(request_id: str):
    db = SessionLocal()
    try:
        # Update status to PROCESSING
        request = db.query(Request).filter(Request.request_id == request_id).first()
        if not request:
            return
        
        request.status = RequestStatus.PROCESSING
        request.updated_at = datetime.utcnow()
        db.commit()

        # Get all products for this request
        products = db.query(Product).filter(Product.request_id == request_id).all()

        output_urls = []
        for product in products:
            input_urls = [url.strip() for url in product.input_image_urls.split(',') if url.strip()]
            processed_urls = []
            
            for url in input_urls:
                if not url.startswith(('http://', 'https://')):
                    print(f"Skipping invalid URL: {url}")
                    processed_urls.append(None)
                    continue
                try:
                    # Download image
                    response = requests.get(url.strip())
                    img = Image.open(BytesIO(response.content))
                    
                    # Compress to 50% quality
                    output_buffer = BytesIO()
                    img.save(output_buffer, format=img.format, quality=50)
                    output_buffer.seek(0)
                    
                    # Save processed image (in a real system, upload to cloud storage)
                    filename = f"{uuid.uuid4()}.{img.format.lower()}"
                    output_path = os.path.join(PROCESSED_DIR, filename)
                    with open(output_path, 'wb') as f:
                        f.write(output_buffer.getvalue())
                    
                    # Construct processed URL using the base URL
                    processed_url = f"{PROCESSED_URL_BASE}{filename}"
                    processed_urls.append(processed_url)
                    
                except Exception as e:
                    print(f"Error processing image {url}: {str(e)}")
                    processed_urls.append(None)  # Keep sequence but mark as failed
            # Convert None to empty string for joining
            processed_urls_str = [url if url is not None else "" for url in processed_urls]
            
            # Update product with processed URLs
            product.output_image_urls = ','.join(processed_urls_str)
            db.commit()
            time.sleep(1)  # Rate limiting

        # Update status to COMPLETED
        request.status = RequestStatus.COMPLETED
        request.updated_at = datetime.utcnow()
        db.commit()

        # Trigger webhook
        trigger_webhook(request_id, RequestStatus.COMPLETED)

    except Exception as e:
        # Update status to FAILED
        request.status = RequestStatus.FAILED
        request.updated_at = datetime.utcnow()
        db.commit()
        trigger_webhook(request_id, RequestStatus.FAILED)
        print(f"Processing failed: {str(e)}")
    finally:
        db.close()
