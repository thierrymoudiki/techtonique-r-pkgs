import json
import os
import uvicorn
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, File, Request, Query, HTTPException, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
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
    Base.metadata.create_all(bind=engine)
except Exception as e:
    raise RuntimeError(f"Failed to connect to database: {str(e)}")

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
    version: str, 
    platform: str = "source",
    db: Session = Depends(get_db)
):
    try:
        today = date.today()
        
        # Get or create download record - using get() with synchronize_session
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
            package_url = f"{base_url}/bin/windows/contrib/{version}/{package}_{version}.zip"
        elif platform == "macos":
            package_url = f"{base_url}/bin/macosx/contrib/{version}/{package}_{version}.tgz"
        else:  # source
            package_url = f"{base_url}/src/contrib/{package}_{version}.tar.gz"
        
        return RedirectResponse(url=package_url)
        
    except Exception as e:
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

class Download(Base):
    __tablename__ = "downloads"
    id = Column(Integer, primary_key=True)         # 4 bytes
    package = Column(String)                       # variable
    date = Column(Date)                           # 4 bytes
    count = Column(Integer)                       # 4 bytes
    platform = Column(String)                     # variable

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, log_level="info")