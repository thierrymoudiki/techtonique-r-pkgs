import json
import os
import uvicorn
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, File, Request, Query, HTTPException, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, Column, Integer, String, Date, desc, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Load environment variables from .env file
load_dotenv()

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
# Add SessionMiddleware with a secret key
app.add_middleware(
    SessionMiddleware,
    secret_key="your-secret-key-here"  # Replace with a secure secret key
)

# Mount static files directory
app.mount("/css", StaticFiles(directory="templates/css"), name="css")
app.mount("/images", StaticFiles(directory="templates/images"), name="images")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def get_index(request: Request, db: Session = Depends(get_db)):
    try:
        packages = {}
        r_packages_dir = Path("r-packages")
        
        # Get latest version for each package from r-packages/src/contrib
        src_contrib = r_packages_dir / "src" / "contrib"
        if src_contrib.exists():
            for tar_gz in src_contrib.glob("*.tar.gz"):
                package_name = tar_gz.name.split("_")[0]
                version = tar_gz.name.split("_")[1].replace(".tar.gz", "")
                if package_name not in packages:
                    packages[package_name] = {
                        "package": package_name,
                        "version": version,
                        "platforms": {
                            "source": {
                                "status": "SUCCESS",  # If file exists, it's a success
                                "build_time": datetime.fromtimestamp(tar_gz.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                            }
                        }
                    }

        # Check Windows binaries for all R versions
        for r_version in ["4.2", "4.3", "4.4"]:
            win_dir = r_packages_dir / "bin" / "windows" / "contrib" / r_version
            if win_dir.exists():
                for zip_file in win_dir.glob("*.zip"):
                    package_name = zip_file.name.split("_")[0]
                    if package_name in packages:
                        packages[package_name]["platforms"]["windows"] = {
                            "status": "SUCCESS",
                            "build_time": datetime.fromtimestamp(zip_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                            "r_version": r_version
                        }

        # Check macOS binaries for all R versions
        for r_version in ["4.2", "4.3", "4.4"]:
            mac_dir = r_packages_dir / "bin" / "macosx" / "contrib" / r_version
            if mac_dir.exists():
                for tgz_file in mac_dir.glob("*.tgz"):
                    package_name = tgz_file.name.split("_")[0]
                    if package_name in packages:
                        packages[package_name]["platforms"]["macos"] = {
                            "status": "SUCCESS",
                            "build_time": datetime.fromtimestamp(tgz_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                            "r_version": r_version
                        }

        # Read build status files to get list of all packages that should exist
        for json_file in r_packages_dir.glob("build_status_*.json"):
            with open(json_file) as f:
                build_info = json.load(f)
                platform = build_info.get("platform", "unknown")
                for pkg_name, pkg_info in build_info.get("packages", {}).items():
                    if pkg_name not in packages:
                        # Package was in build status but no file exists
                        if pkg_name not in packages:
                            packages[pkg_name] = {
                                "package": pkg_name,
                                "version": "",
                                "platforms": {}
                            }
                        packages[pkg_name]["platforms"][platform] = {
                            "status": "FAILED",  # No file exists, so it failed
                            "build_time": pkg_info.get("build_time", ""),
                            "error_message": "No package file found"
                        }

        return templates.TemplateResponse(
            "index.html", 
            {
                "request": request, 
                "year": datetime.now().year,
                "packages": packages,
                "downloads": db.query(Download).order_by(desc(Download.date)).all()
            }
        )
    except Exception as e:
        print(f"Error in get_index: {str(e)}")
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
        base_url = "https://r-packages.techtonique.net"  # Using the existing domain
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

@app.get("/download/source/{package}")
async def download_source_package(
    package: str, 
    version: str = Query(..., description="R package version"),
    db: Session = Depends(get_db)
):
    try:
        today = date.today()
        file_path = f"r-packages/src/contrib/{package}_{version}.tar.gz"
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"Package file not found: {file_path}"
            )
            
        # Record the download
        download = db.query(Download).filter(
            Download.package == package,
            Download.date == today,
            Download.platform == "source"
        ).first()
        
        if not download:
            download = Download(
                package=package,
                date=today,
                count=1,
                platform="source"
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
        
        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type="application/octet-stream"
        )
        
    except Exception as e:
        print(f"Error in download_source_package: {str(e)}")
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

@app.get("/src/contrib/PACKAGES")
@app.get("/src/contrib/PACKAGES.gz")
@app.get("/src/contrib/PACKAGES.rds")
@app.get("/bin/windows/contrib/{r_version}/PACKAGES")
@app.get("/bin/windows/contrib/{r_version}/PACKAGES.gz")
@app.get("/bin/windows/contrib/{r_version}/PACKAGES.rds")
@app.get("/bin/macosx/contrib/{r_version}/PACKAGES")
@app.get("/bin/macosx/contrib/{r_version}/PACKAGES.gz")
@app.get("/bin/macosx/contrib/{r_version}/PACKAGES.rds")
async def serve_packages_file(request: Request, r_version: str = None):
    try:
        # Remove the leading slash and add r-packages prefix
        url_path = request.url.path.lstrip('/')
        file_path = f"r-packages/{url_path}"
        
        # Debug logging
        print(f"Attempting to serve PACKAGES file from: {file_path}")

        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404, 
                detail=f"PACKAGES file not found at: {file_path}"
            )

        # Determine media type
        if file_path.endswith('.gz'):
            media_type = 'application/gzip'
        elif file_path.endswith('.rds'):
            media_type = 'application/octet-stream'
        else:
            media_type = 'text/plain'

        return FileResponse(
            file_path,
            media_type=media_type
        )
        
    except Exception as e:
        print(f"Error serving PACKAGES file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/src/contrib/{file_name}")
@app.get("/bin/windows/contrib/{r_version}/{file_name}")
@app.get("/bin/macosx/contrib/{r_version}/{file_name}")
async def serve_package(
    request: Request,
    file_name: str,
    r_version: str = None,
    db: Session = Depends(get_db)
):
    try:
        # Skip if requesting PACKAGES files
        if file_name in ["PACKAGES", "PACKAGES.gz", "PACKAGES.rds"]:
            raise HTTPException(status_code=404, detail="Use PACKAGES endpoint")
            
        # Remove the leading slash and add r-packages prefix
        url_path = request.url.path.lstrip('/')
        file_path = f"r-packages/{url_path}"
        
        # Parse package name and version from file_name
        parts = file_name.rsplit("_", 1)
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid file name format")
        
        package = parts[0]
        version = parts[1].split(".")[0]  # Get version before file extension
        
        # Determine platform from path
        if "windows" in str(request.url):
            platform = "windows"
        elif "macosx" in str(request.url):
            platform = "macos"
        else:
            platform = "source"

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
        
        return FileResponse(
            file_path,
            filename=file_name,
            media_type="application/octet-stream"
        )
        
    except Exception as e:
        print(f"Error serving package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/downloads", response_class=HTMLResponse)
async def get_downloads(request: Request, db: Session = Depends(get_db)):
    try:
        # Use SQL to aggregate downloads by month and package
        monthly_downloads = db.execute(
            text("""
                SELECT 
                    package,
                    DATE_TRUNC('month', date) as month,
                    platform,
                    SUM(count) as total_count
                FROM downloads
                GROUP BY package, DATE_TRUNC('month', date), platform
                ORDER BY DATE_TRUNC('month', date) DESC, package, platform
            """)
        ).fetchall()
        
        # Organize the data by month and package
        downloads_by_month = {}
        for row in monthly_downloads:
            month_str = row.month.strftime("%Y-%m")
            if month_str not in downloads_by_month:
                downloads_by_month[month_str] = {}
            
            if row.package not in downloads_by_month[month_str]:
                downloads_by_month[month_str][row.package] = {
                    'total': 0,
                    'platforms': {}
                }
            
            downloads_by_month[month_str][row.package]['platforms'][row.platform] = row.total_count
            downloads_by_month[month_str][row.package]['total'] += row.total_count
        
        return templates.TemplateResponse(
            "downloads.html",
            {
                "request": request,
                "downloads_by_month": downloads_by_month,
                "year": datetime.now().year
            }
        )
    except Exception as e:
        print(f"Error in get_downloads: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/packages", response_class=HTMLResponse)
async def get_packages(request: Request, db: Session = Depends(get_db)):
    try:
        packages = {}
        r_packages_dir = Path("r-packages")
        
        # Get latest version for each package from r-packages/src/contrib
        src_contrib = r_packages_dir / "src" / "contrib"
        if src_contrib.exists():
            for tar_gz in src_contrib.glob("*.tar.gz"):
                package_name = tar_gz.name.split("_")[0]
                version = tar_gz.name.split("_")[1].replace(".tar.gz", "")
                if package_name not in packages:
                    packages[package_name] = {
                        "package": package_name,
                        "version": version,
                        "platforms": {
                            "source": {
                                "status": "SUCCESS",  # If file exists, it's a success
                                "build_time": datetime.fromtimestamp(tar_gz.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                            }
                        }
                    }

        # Check Windows binaries for all R versions
        for r_version in ["4.2", "4.3", "4.4"]:
            win_dir = r_packages_dir / "bin" / "windows" / "contrib" / r_version
            if win_dir.exists():
                for zip_file in win_dir.glob("*.zip"):
                    package_name = zip_file.name.split("_")[0]
                    if package_name in packages:
                        packages[package_name]["platforms"]["windows"] = {
                            "status": "SUCCESS",
                            "build_time": datetime.fromtimestamp(zip_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                            "r_version": r_version
                        }

        # Check macOS binaries for all R versions
        for r_version in ["4.2", "4.3", "4.4"]:
            mac_dir = r_packages_dir / "bin" / "macosx" / "contrib" / r_version
            if mac_dir.exists():
                for tgz_file in mac_dir.glob("*.tgz"):
                    package_name = tgz_file.name.split("_")[0]
                    if package_name in packages:
                        packages[package_name]["platforms"]["macos"] = {
                            "status": "SUCCESS",
                            "build_time": datetime.fromtimestamp(tgz_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                            "r_version": r_version
                        }

        # Read build status files to get list of all packages that should exist
        for json_file in r_packages_dir.glob("build_status_*.json"):
            with open(json_file) as f:
                build_info = json.load(f)
                platform = build_info.get("platform", "unknown")
                for pkg_name, pkg_info in build_info.get("packages", {}).items():
                    if pkg_name not in packages:
                        # Package was in build status but no file exists
                        if pkg_name not in packages:
                            packages[pkg_name] = {
                                "package": pkg_name,
                                "version": "",
                                "platforms": {}
                            }
                        packages[pkg_name]["platforms"][platform] = {
                            "status": "FAILED",  # No file exists, so it failed
                            "build_time": pkg_info.get("build_time", ""),
                            "error_message": "No package file found"
                        }

        return templates.TemplateResponse(
            "packages.html", 
            {
                "request": request, 
                "year": datetime.now().year,
                "packages": packages
            }
        )
    except Exception as e:
        print(f"Error in get_packages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, log_level="info")