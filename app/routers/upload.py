from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from datetime import datetime
import csv  # Use standard csv module
import uuid
import aiofiles
import os
from app.models.request import Request, RequestStatus
from app.models.product import Product
from app.core.database import SessionLocal
from app.workers.image_processor import process_images
from typing import Optional

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    webhook_url: Optional[str] = None
):
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    # Generate unique request ID
    request_id = str(uuid.uuid4())
    
    # Save the file temporarily
    file_path = os.path.join(UPLOAD_DIR, f"{request_id}.csv")
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # Store request and products in database
    db = SessionLocal()
    try:
        # Create the request entry first
        db_request = Request(
            request_id=request_id,
            status=RequestStatus.PENDING,
            webhook_url=webhook_url
        )
        db.add(db_request)
        db.commit() # Commit request first

        # Process CSV using standard csv module
        products_to_add = []
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader) # Skip header row
            
            # Basic header validation (adjust indices if needed)
            expected_header = ['S. No.', 'Product Name', 'Input Image Urls']
            if header != expected_header:
                 # Rollback request creation if header is wrong
                db.delete(db_request)
                db.commit()
                raise HTTPException(status_code=400, detail=f"Invalid CSV header. Expected: {expected_header}, Got: {header}")

            for i, row in enumerate(reader):
                # Check if we have at least the first 3 expected columns
                if len(row) < 3: 
                    # Rollback request creation if row format is too short
                    db.delete(db_request)
                    db.commit()
                    raise HTTPException(status_code=400, detail=f"Invalid row format at line {i+2}. Expected at least 3 columns, got {len(row)}.")
                
                # Extract data by index, joining columns from index 2 onwards for URLs
                serial_num = str(row[0]).strip()
                product_name = str(row[1]).strip()
                # Join all parts from the 3rd column onwards with a comma
                input_urls = ','.join(str(part).strip() for part in row[2:]) 

                # Basic validation (optional, can add more)
                if not serial_num or not product_name or not input_urls:
                     # Rollback request creation if essential data missing
                    db.delete(db_request)
                    db.commit()
                    raise HTTPException(status_code=400, detail=f"Missing data in row {i+2}.")

                product = Product(
                    request_id=request_id,
                    serial_number=serial_num,
                    product_name=product_name,
                    input_image_urls=input_urls # Store the raw string
                )
                products_to_add.append(product)
        
        # Add all products in one go after validation
        db.add_all(products_to_add)
        db.commit()

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions directly
        raise http_exc
    except Exception as e:
        db.rollback() # Rollback any partial commits if general error occurs
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
    finally:
        db.close()

    # Start async processing
    background_tasks.add_task(process_images, request_id)

    return JSONResponse(
        content={"request_id": request_id},
        status_code=202
    )
