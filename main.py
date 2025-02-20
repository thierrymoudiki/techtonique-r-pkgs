import json
import os
import uvicorn
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, File, Request, Query, HTTPException, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, Column, Integer, String, Date, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Add error handling for database connection
try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    raise RuntimeError(f"Failed to connect to database: {str(e)}")

class Download(Base):
    __tablename__ = "downloads"
    id = Column(Integer, primary_key=True)         # 4 bytes
    package = Column(String)                       # variable
    date = Column(Date)                           # 4 bytes
    count = Column(Integer)                       # 4 bytes
    platform = Column(String)                     # variable

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def get_index(request: Request, db: Session = Depends(get_db)):
    try:
        downloads = db.query(Download).order_by(desc(Download.date)).all()
        return templates.TemplateResponse(
            "index.html", 
            {
                "request": request, 
                "year": datetime.now().year,
                "downloads": downloads
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{package}")
async def download_package(
    package: str, 
    version: str = Query(..., description="R package version"),
    platform: str = Query(default="source", description="Platform (windows/macos/source)"),
    r_version: str = Query(default="4.3", description="R version (e.g. 4.3)"),
    db: Session = Depends(get_db)
):
    try:
        today = date.today()
        
        # Log the incoming request
        print(f"Download request: package={package}, version={version}, platform={platform}")
        
        # Get or create download record
        download = db.query(Download).filter(
            Download.package == package,
            Download.date == today,
            Download.platform == platform
        ).first()
        
        if not download:
            download = Download(
                package=package,
                date=today,
                count=1,
                platform=platform
            )
            db.add(download)
        else:
            # Use SQL update for atomic increment
            db.query(Download).filter(
                Download.id == download.id
            ).update(
                {"count": Download.count + 1},
                synchronize_session=False
            )
        
        db.commit()
        
        # Construct package URL based on platform
        base_url = "https://techtonique.github.io/r-packages"
        if platform == "windows":
            package_url = f"{base_url}/bin/windows/contrib/{r_version}/{package}_{version}.zip"
        elif platform == "macos":
            package_url = f"{base_url}/bin/macosx/contrib/{package}_{version}.tgz"
        else:  # source
            package_url = f"{base_url}/src/contrib/{package}_{version}.tar.gz"
        
        # Log the redirect URL
        print(f"Redirecting to: {package_url}")
        
        return RedirectResponse(url=package_url)
        
    except Exception as e:
        print(f"Error in download_package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/{date}/{package}")
async def get_stats(date: str, package: str, db: Session = Depends(get_db)):
    try:
        downloads = db.query(Download).filter(
            Download.package == package,
            Download.date == date
        ).all()
        
        if not downloads:
            return {"package": package, "date": date, "total_count": 0, "by_platform": {}}
            
        total_count = sum(d.count for d in downloads)
        by_platform = {
            d.platform: {
                "count": d.count,
                "date": d.date.isoformat()
            } for d in downloads
        }
            
        return {
            "package": package,
            "date": date,
            "total_count": total_count,
            "by_platform": by_platform
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/today")
async def get_today_stats(db: Session = Depends(get_db)):
    try:
        today = date.today()
        downloads = db.query(Download).filter(Download.date == today).all()
        return [
            {
                "package": d.package,
                "date": d.date.isoformat(),
                "count": d.count,
                "platform": d.platform
            } 
            for d in downloads
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/r-packages/src/contrib/{file_name}")
@app.get("/r-packages/bin/windows/contrib/{r_version}/{file_name}")
@app.get("/r-packages/bin/macosx/contrib/{r_version}/{file_name}")
async def serve_package(
    request: Request,  # Add request parameter
    file_name: str,
    r_version: str = None,
    db: Session = Depends(get_db)
):
    try:
        # Parse package name and version from file_name
        parts = file_name.rsplit("_", 1)
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid file name format")
        
        package = parts[0]
        version = parts[1].split(".")[0]  # Get version before file extension
        
        # Determine platform from path
        if "windows" in str(request.url):
            platform = "windows"
            file_path = f"r-packages/bin/windows/contrib/{r_version}/{file_name}"
        elif "macosx" in str(request.url):
            platform = "macos"
            file_path = f"r-packages/bin/macosx/contrib/{r_version}/{file_name}"
        else:
            platform = "source"
            file_path = f"r-packages/src/contrib/{file_name}"

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404, 
                detail=f"Package file not found: {file_path}"
            )

        # Record the download
        today = date.today()
        download = db.query(Download).filter(
            Download.package == package,
            Download.date == today,
            Download.platform == platform
        ).first()
        
        if not download:
            download = Download(
                package=package,
                date=today,
                count=1,
                platform=platform
            )
            db.add(download)
        else:
            db.query(Download).filter(
                Download.id == download.id
            ).update(
                {"count": Download.count + 1},
                synchronize_session=False
            )
        
        db.commit()
        
        # Log the download
        print(f"Package download: {package} {version} for {platform}")
        
        # Serve the file
        return FileResponse(
            file_path,
            filename=file_name,
            media_type="application/octet-stream"
        )
        
    except Exception as e:
        print(f"Error serving package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/r-packages/src/contrib/PACKAGES")
@app.get("/r-packages/bin/windows/contrib/{r_version}/PACKAGES")
@app.get("/r-packages/bin/macosx/contrib/{r_version}/PACKAGES")
async def serve_packages_file(request: Request, r_version: str = None):
    try:
        # Determine which PACKAGES file to serve based on the URL
        if "windows" in str(request.url):
            file_path = f"r-packages/bin/windows/contrib/{r_version}/PACKAGES"
        elif "macosx" in str(request.url):
            file_path = f"r-packages/bin/macosx/contrib/{r_version}/PACKAGES"
        else:  # source
            file_path = "r-packages/src/contrib/PACKAGES"

        # Debug logging
        print(f"Attempting to serve PACKAGES file from: {file_path}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Directory contents: {os.listdir('.')}")
        if os.path.exists('r-packages'):
            print(f"r-packages contents: {os.listdir('r-packages')}")

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404, 
                detail=f"PACKAGES file not found at: {file_path}. Working directory: {os.getcwd()}"
            )

        # Serve the file
        return FileResponse(
            file_path,
            media_type="text/plain",
            filename="PACKAGES"  # Explicitly set filename
        )
        
    except Exception as e:
        print(f"Error serving PACKAGES file: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error serving PACKAGES file: {str(e)}"
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, log_level="info")