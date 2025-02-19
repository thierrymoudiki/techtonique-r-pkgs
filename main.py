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
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Download(Base):
    __tablename__ = "downloads"
    id = Column(Integer, primary_key=True)
    package = Column(String)
    date = Column(Date)
    count = Column(Integer)
    platform = Column(String)

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
    # Get download stats for display
    downloads = db.query(Download).order_by(desc(Download.date)).all()
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "year": datetime.now().year,
            "downloads": downloads
        }
    )

@app.get("/download/{package}")
async def download_package(
    package: str, 
    version: str, 
    platform: str = "source",
    db: Session = Depends(get_db)
):
    try:
        today = date.today()
        
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
            download.count += 1
        
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
        download = db.query(Download).filter(
            Download.package == package,
            Download.date == date
        ).first()
        
        if not download:
            return {"package": package, "date": date, "count": 0}
            
        return {
            "package": download.package,
            "date": download.date.isoformat(),
            "count": download.count,
            "platform": download.platform
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)