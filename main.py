from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="SplitBox")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", name="landing")
def landing(request: Request):
    return templates.TemplateResponse(
        request,
        "landing.html",
        {"current_user": None, "year": datetime.now().year},
    )


@app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exception: StarletteHTTPException):
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "current_user": None,
            "year": datetime.now().year,
            "status_code": exception.status_code,
            "message": exception.detail,
        },
        status_code=exception.status_code,
    )
