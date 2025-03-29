from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import requests
from app.models.request import Request, RequestStatus
from app.models.product import Product
from app.core.database import SessionLocal
from typing import List, Dict

router = APIRouter()

@router.get("/status/{request_id}")
async def get_status(request_id: str):
    db = SessionLocal()
    try:
        # Get request status
        request = db.query(Request).filter(Request.request_id == request_id).first()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        # Get products for this request and ensure they exist
        products = db.query(Product).filter(Product.request_id == request_id).all()
        if not products:
            raise HTTPException(status_code=404, detail="No products found for this request")

        # Format response with proper null checks
        response = {
            "request_id": request_id,
            "status": request.status.value,
            "created_at": request.created_at.isoformat() if request.created_at else None,
            "updated_at": request.updated_at.isoformat() if request.updated_at else None,
            "products": [
                {
                    "serial_number": p.serial_number,
                    "product_name": p.product_name,
                    # Split input URLs, filter empty strings just in case
                    "input_image_urls": [url for url in p.input_image_urls.split(',') if url] if p.input_image_urls else [],
                     # Split output URLs. Keep empty strings to indicate failed processing for that slot.
                    "output_image_urls": p.output_image_urls.split(',') if p.output_image_urls is not None else [] 
                }
                for p in products
            ]
        }

        return JSONResponse(content=response)
    except Exception as e:
        print(f"Error checking status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
    finally:
        db.close()

async def trigger_webhook(request_id: str, status: RequestStatus):
    db = SessionLocal()
    try:
        request = db.query(Request).filter(Request.request_id == request_id).first()
        if request and request.webhook_url:
            payload = {
                "request_id": request_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            requests.post(request.webhook_url, json=payload)
    except Exception as e:
        print(f"Webhook failed: {str(e)}")
    finally:
        db.close()
