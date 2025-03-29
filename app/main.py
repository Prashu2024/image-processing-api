from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles # Import StaticFiles
from app.core.database import engine, Base
from app.routers import upload, status
import uvicorn
import os # Import os

# Create all database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Image Processing API",
    description="API for processing product images from CSV files",
    version="0.1.0"
)

# Mount static files directory for processed images
processed_dir = "processed"
os.makedirs(processed_dir, exist_ok=True) # Ensure directory exists
app.mount("/processed", StaticFiles(directory=processed_dir), name="processed")

# Include routers
app.include_router(upload.router)
app.include_router(status.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
