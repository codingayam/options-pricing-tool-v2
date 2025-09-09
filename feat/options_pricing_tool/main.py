from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import os

from .api.endpoints import router as options_router

# Set up basic logging (actual file logging configured in start_options_tool.py)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Options Pricing Comparison Tool",
    description="Compare market prices with Black-Scholes and Power Law pricing models",
    version="1.0.0"
)

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Set up templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)

# Include API routes
app.include_router(options_router)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main analysis interface"""
    return templates.TemplateResponse("analysis.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Options Pricing Tool is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)