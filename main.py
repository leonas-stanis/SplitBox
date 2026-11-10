import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from auth import AuthRequired, CurrentUser, PageUser, SessionDep
from database import Base, engine
from formatters import format_clock, format_date, format_delta
from security import get_secret_key, hash_password, verify_password
import models

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters.update(
    clock=format_clock,
    delta=format_delta,
    date=format_date,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="SplitBox", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=get_secret_key(),
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,20}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def flash(request: Request, message: str, tone: str = "info") -> None:
    request.session.setdefault("flashes", []).append(
        {"message": message, "tone": tone}
    )


def page(
    request: Request,
    template: str,
    *,
    user: models.User | None = None,
    status_code: int = 200,
    **context,
):
    context["current_user"] = user
    context["year"] = datetime.now().year
    context["flashes"] = request.session.pop("flashes", [])
    return templates.TemplateResponse(
        request, template, context, status_code=status_code
    )


def registration_error(
    db: SessionDep, username: str, email: str, password: str, confirm: str
) -> str | None:
    if not USERNAME_PATTERN.fullmatch(username):
        return "Username must be 3–20 characters using letters, numbers, dots, dashes or underscores."
    if not EMAIL_PATTERN.fullmatch(email):
        return "Enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password != confirm:
        return "The passwords do not match."
    if db.scalar(
        select(models.User.id).where(
            func.lower(models.User.username) == username.lower()
        )
    ):
        return "That username is already taken."
    if db.scalar(
        select(models.User.id).where(models.User.email == email.lower())
    ):
        return "An account with that email already exists."
    return None


@app.get("/", name="landing")
def landing(request: Request, user: CurrentUser):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return page(request, "landing.html")


@app.get("/register", name="register_page")
def register_page(request: Request, user: CurrentUser):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return page(request, "register.html")


@app.post("/register", name="register")
def register(
    request: Request,
    db: SessionDep,
    username: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    confirm: Annotated[str, Form()] = "",
):
    username = username.strip()
    email = email.strip().lower()
    problem = registration_error(db, username, email, password, confirm)
    if problem:
        return page(
            request,
            "register.html",
            status_code=400,
            error=problem,
            form={"username": username, "email": email},
        )

    password_hash, password_salt = hash_password(password)
    user = models.User(
        username=username,
        email=email,
        password_hash=password_hash,
        password_salt=password_salt,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return page(
            request,
            "register.html",
            status_code=400,
            error="That account already exists.",
            form={"username": username, "email": email},
        )

    db.refresh(user)
    request.session.clear()
    request.session["user_id"] = user.id
    flash(request, "Account created. Let's add a game.", "success")
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/login", name="login_page")
def login_page(request: Request, user: CurrentUser):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return page(request, "login.html")


@app.post("/login", name="login")
def login(
    request: Request,
    db: SessionDep,
    identifier: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
):
    identifier = identifier.strip()
    user = db.scalar(
        select(models.User).where(
            or_(
                func.lower(models.User.username) == identifier.lower(),
                func.lower(models.User.email) == identifier.lower(),
            )
        )
    )

    if user is None or not verify_password(
        password, user.password_hash, user.password_salt
    ):
        return page(
            request,
            "login.html",
            status_code=400,
            error="Incorrect username/email or password.",
            form={"identifier": identifier},
        )

    request.session.clear()
    request.session["user_id"] = user.id
    flash(request, f"Welcome back, {user.username}.", "success")
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/logout", name="logout")
def logout(request: Request):
    request.session.clear()
    flash(request, "Signed out.")
    return RedirectResponse("/", status_code=303)


@app.get("/dashboard", name="dashboard")
def dashboard(request: Request, user: PageUser):
    return page(request, "dashboard.html", user=user)


@app.exception_handler(AuthRequired)
def auth_required_handler(request: Request, exception: AuthRequired):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exception: StarletteHTTPException):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail": exception.detail},
        )
    return page(
        request,
        "error.html",
        status_code=exception.status_code,
        message=exception.detail,
    )
