import json
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import (
    FastAPI,
    File,
    Request,
    Query,
    HTTPException,
    Depends,
    Response,
)
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, RedirectResponse
from fastapi import HTTPException
from fastapi.responses import FileResponse

app = FastAPI()

templates = Jinja2Templates(directory="templates")

PACKAGE_FILE = Path(__file__).parent / "packages.json"
DATABASE_FILE = Path(__file__).parent / "database.db"
PACKAGE_DIR = Path(__file__).parent / "packages"

def load_packages():
    print(f"\n\n PACKAGE_FILE: {PACKAGE_FILE}")
    with open(PACKAGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package TEXT,
            platform TEXT,
            timestamp TEXT,
            ip TEXT
        )
        """
    )
    conn.commit()
    return conn

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "year": datetime.now().year})


@app.get("/PACKAGES")
async def serve_packages_metadata(request: Request):
    """Serve the PACKAGES metadata file for R"""
    packages = load_packages()
    
    # Add build status and local source path to each package
    for pkg in packages:
        pkg_filename = pkg['url'].split('/')[-1]
        pkg_file = PACKAGE_DIR / pkg_filename
        pkg['build_exists'] = pkg_file.exists()
        # Get package name without version and extension
        pkg_name = pkg_filename.split('_')[0]
        pkg['source_path'] = f"/packages/{pkg_name}"
    
    return templates.TemplateResponse(
        "packages.html", 
        {
            "request": request, 
            "packages": packages,
            "year": datetime.now().year
        }
    )

@app.get("/src/contrib/{package_file}")
async def download_package_file(package_file: str, request: Request):
    """Serve package files"""
    package_path = PACKAGE_DIR / package_file
    if not package_path.exists():
        raise HTTPException(status_code=404, detail="Package not found")

    ip = request.client.host
    conn = get_db_connection()
    conn.execute("INSERT INTO downloads (package, platform, timestamp, ip) VALUES (?, ?, ?, ?)",
                 (package_file, "source", datetime.utcnow().isoformat(), ip))
    conn.commit()
    conn.close()

    return FileResponse(package_path, filename=package_file)

@app.get("/stats")
async def get_download_stats():
    """Returns download statistics"""
    conn = get_db_connection()
    cursor = conn.execute("SELECT package, platform, COUNT(*) as downloads FROM downloads GROUP BY package, platform")
    stats = [{"package": row[0], "platform": row[1], "downloads": row[2]} for row in cursor.fetchall()]
    conn.close()
    return JSONResponse(content=stats)

@app.get("/download/{package_name}")
async def download_package(package_name: str):
    """Serve the actual package files"""
    package_path = PACKAGE_DIR / package_name
    if not package_path.exists():
        raise HTTPException(status_code=404, detail="Package not found")
    return FileResponse(package_path)
