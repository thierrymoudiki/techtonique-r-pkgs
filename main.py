import json
import os
import uvicorn

from datetime import date
from pathlib import Path
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
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, RedirectResponse
from fastapi import HTTPException
from fastapi.responses import FileResponse

app = FastAPI()

templates = Jinja2Templates(directory="templates")

STATS_DIR = Path("stats")
STATS_DIR.mkdir(exist_ok=True)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "year": datetime.now().year})

@app.get("/download/{package}")
async def download_package(package: str, version: str, platform: str = "source"):
    try:
        # Construct today's stats file path
        today = date.today().isoformat()
        stats_file = STATS_DIR / f"{today}-{package}-downloads.json"
        
        # Read current count
        if stats_file.exists():
            with open(stats_file) as f:
                stats = json.load(f)
                count = stats["count"]
        else:
            count = 0
            
        # Update count
        stats = {
            "package": package,
            "date": today,
            "count": count + 1,
            "platform": platform,
            "last_update": date.today().isoformat()
        }
        
        # Save updated stats
        with open(stats_file, "w") as f:
            json.dump(stats, f, indent=2)
            
        # Construct package URL based on platform
        base_url = "https://techtonique.github.io/r-packages"
        if platform == "windows":
            # Windows binaries are in bin/windows/contrib/[R-version]
            package_url = f"{base_url}/bin/windows/contrib/{version}/{package}_{version}.zip"
        elif platform == "macos":
            # macOS binaries are in bin/macosx/contrib/[R-version]
            package_url = f"{base_url}/bin/macosx/contrib/{version}/{package}_{version}.tgz"
        else:  # source
            # Source packages are directly in src/contrib
            package_url = f"{base_url}/src/contrib/{package}_{version}.tar.gz"
        
        # Redirect to actual package
        return RedirectResponse(url=package_url)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/{date}/{package}")
async def get_stats(date: str, package: str):
    try:
        stats_file = STATS_DIR / f"{date}-{package}-downloads.json"
        if not stats_file.exists():
            return {"package": package, "date": date, "count": 0}
            
        with open(stats_file) as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/today")
async def get_today_stats():
    try:
        today = date.today().isoformat()
        stats = []
        for stats_file in STATS_DIR.glob(f"{today}-*-downloads.json"):
            with open(stats_file) as f:
                stats.append(json.load(f))
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    is_heroku = "PORT" in os.environ

    if is_heroku:
        uvicorn.run("main:app", host="0.0.0.0", port=port)  # Use app instead of cors_app
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000)  # Use app instead of cors_app