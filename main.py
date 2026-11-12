import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from auth import ApiUser, AuthRequired, CurrentUser, PageUser, SessionDep
from database import Base, engine
from formatters import format_clock, format_date, format_delta, parse_time_input
from security import get_secret_key, hash_password, verify_password
import models
import schemas

logger = logging.getLogger("splitbox.pi5")

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
    https_only=os.environ.get("COOKIE_SECURE", "0") == "1",
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


def game_summary(game: models.Game) -> dict:
    best_ms = None
    for category in game.categories:
        best_run = category.personal_best
        if best_run is not None:
            best_ms = (
                best_run.total_ms
                if best_ms is None
                else min(best_ms, best_run.total_ms)
            )
    return {
        "game": game,
        "category_count": len(game.categories),
        "best_ms": best_ms,
    }


def owned_game(db: SessionDep, user: models.User, game_id: int) -> models.Game:
    game = db.get(models.Game, game_id)
    if game is None or game.user_id != user.id:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def owned_category(
    db: SessionDep, user: models.User, category_id: int
) -> models.Category:
    category = db.get(models.Category, category_id)
    if category is None or category.game.user_id != user.id:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def owned_split(db: SessionDep, user: models.User, split_id: int) -> models.Split:
    split = db.get(models.Split, split_id)
    if split is None or split.category.game.user_id != user.id:
        raise HTTPException(status_code=404, detail="Split not found")
    return split


def comparison_for(category: models.Category) -> dict | None:
    personal_best = category.personal_best
    if personal_best is not None:
        return {
            "kind": "pb",
            "label": "PB",
            "total_ms": personal_best.total_ms,
            "splits": {
                str(run_split.split_id): run_split.cumulative_ms
                for run_split in personal_best.splits
                if run_split.split_id is not None
            },
        }

    targeted = [split for split in category.splits if split.target_ms is not None]
    if targeted:
        last = category.splits[-1] if category.splits else None
        return {
            "kind": "target",
            "label": "Target",
            "total_ms": last.target_ms if last and last.target_ms is not None else None,
            "splits": {str(split.id): split.target_ms for split in targeted},
        }

    return None


def best_segments_for(category: models.Category) -> dict[str, int]:
    best: dict[str, int] = {}
    for run in category.runs:
        for run_split in run.splits:
            if run_split.split_id is None:
                continue
            key = str(run_split.split_id)
            if key not in best or run_split.segment_ms < best[key]:
                best[key] = run_split.segment_ms
    return best


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
def dashboard(request: Request, db: SessionDep, user: PageUser):
    games = db.scalars(
        select(models.Game)
        .where(models.Game.user_id == user.id)
        .order_by(models.Game.created_at)
    ).all()
    return page(
        request,
        "dashboard.html",
        user=user,
        game_cards=[game_summary(game) for game in games],
    )


@app.post("/games", name="create_game")
def create_game(
    request: Request,
    db: SessionDep,
    user: PageUser,
    name: Annotated[str, Form()] = "",
    platform: Annotated[str, Form()] = "",
):
    name = name.strip()
    if not name or len(name) > 80:
        flash(request, "Give the game a name (up to 80 characters).", "error")
        return RedirectResponse("/dashboard", status_code=303)

    game = models.Game(
        user_id=user.id,
        name=name,
        platform=platform.strip()[:60],
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    flash(request, f"{game.name} added. Now create a category.", "success")
    return RedirectResponse(f"/games/{game.id}", status_code=303)


@app.get("/games/{game_id}", name="game_page")
def game_page(
    request: Request,
    game_id: int,
    db: SessionDep,
    user: PageUser,
):
    game = owned_game(db, user, game_id)
    return page(request, "game.html", user=user, game=game)


@app.post("/games/{game_id}/update", name="update_game")
def update_game(
    request: Request,
    game_id: int,
    db: SessionDep,
    user: PageUser,
    name: Annotated[str, Form()] = "",
    platform: Annotated[str, Form()] = "",
):
    game = owned_game(db, user, game_id)
    name = name.strip()
    if not name or len(name) > 80:
        flash(request, "Give the game a name (up to 80 characters).", "error")
        return RedirectResponse(f"/games/{game.id}", status_code=303)

    game.name = name
    game.platform = platform.strip()[:60]
    db.commit()
    flash(request, "Game details updated.", "success")
    return RedirectResponse(f"/games/{game.id}", status_code=303)


@app.post("/games/{game_id}/delete", name="delete_game")
def delete_game(
    request: Request,
    game_id: int,
    db: SessionDep,
    user: PageUser,
):
    game = owned_game(db, user, game_id)
    name = game.name
    db.delete(game)
    db.commit()
    flash(request, f"{name} deleted.", "success")
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/games/{game_id}/categories", name="create_category")
def create_category(
    request: Request,
    game_id: int,
    db: SessionDep,
    user: PageUser,
    name: Annotated[str, Form()] = "",
):
    game = owned_game(db, user, game_id)
    name = name.strip()
    if not name or len(name) > 80:
        flash(request, "Give the category a name (up to 80 characters).", "error")
        return RedirectResponse(f"/games/{game.id}", status_code=303)

    category = models.Category(game_id=game.id, name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    flash(request, f"{category.name} added. Build its split route.", "success")
    return RedirectResponse(f"/categories/{category.id}", status_code=303)


@app.get("/categories/{category_id}", name="category_page")
def category_page(
    request: Request,
    category_id: int,
    db: SessionDep,
    user: PageUser,
):
    category = owned_category(db, user, category_id)
    personal_best = category.personal_best
    runs = sorted(category.runs, key=lambda run: run.started_at, reverse=True)
    run_rows = [
        {
            "run": run,
            "is_best": personal_best is not None and run.id == personal_best.id,
            "delta": (
                run.total_ms - personal_best.total_ms
                if personal_best is not None
                else 0
            ),
        }
        for run in runs
    ]
    return page(
        request,
        "category.html",
        user=user,
        category=category,
        comparison=comparison_for(category),
        run_rows=run_rows,
    )


@app.post("/categories/{category_id}/update", name="update_category")
def update_category(
    request: Request,
    category_id: int,
    db: SessionDep,
    user: PageUser,
    name: Annotated[str, Form()] = "",
):
    category = owned_category(db, user, category_id)
    name = name.strip()
    if not name or len(name) > 80:
        flash(request, "Give the category a name (up to 80 characters).", "error")
        return RedirectResponse(f"/categories/{category.id}", status_code=303)

    category.name = name
    db.commit()
    flash(request, "Category renamed.", "success")
    return RedirectResponse(f"/categories/{category.id}", status_code=303)


@app.post("/categories/{category_id}/delete", name="delete_category")
def delete_category(
    request: Request,
    category_id: int,
    db: SessionDep,
    user: PageUser,
):
    category = owned_category(db, user, category_id)
    game_id = category.game_id
    name = category.name
    db.delete(category)
    db.commit()
    flash(request, f"{name} deleted.", "success")
    return RedirectResponse(f"/games/{game_id}", status_code=303)


@app.post("/categories/{category_id}/splits", name="create_split")
def create_split(
    request: Request,
    category_id: int,
    db: SessionDep,
    user: PageUser,
    name: Annotated[str, Form()] = "",
    target: Annotated[str, Form()] = "",
):
    category = owned_category(db, user, category_id)
    name = name.strip()
    if not name or len(name) > 80:
        flash(request, "Give the split a name (up to 80 characters).", "error")
        return RedirectResponse(f"/categories/{category.id}", status_code=303)

    target_text = target.strip()
    target_ms = parse_time_input(target_text) if target_text else None
    if target_text and target_ms is None:
        flash(request, "Use a target like 01:42.018 or 1:02:03.500.", "error")
        return RedirectResponse(f"/categories/{category.id}", status_code=303)

    split = models.Split(
        category_id=category.id,
        name=name,
        target_ms=target_ms,
        position=len(category.splits),
    )
    db.add(split)
    db.commit()
    flash(request, f"{split.name} added to the route.", "success")
    return RedirectResponse(f"/categories/{category.id}", status_code=303)


@app.post("/splits/{split_id}/update", name="update_split")
def update_split(
    request: Request,
    split_id: int,
    db: SessionDep,
    user: PageUser,
    name: Annotated[str, Form()] = "",
    target: Annotated[str, Form()] = "",
):
    split = owned_split(db, user, split_id)
    name = name.strip()
    if not name or len(name) > 80:
        flash(request, "Give the split a name (up to 80 characters).", "error")
        return RedirectResponse(f"/categories/{split.category_id}", status_code=303)

    target_text = target.strip()
    target_ms = parse_time_input(target_text) if target_text else None
    if target_text and target_ms is None:
        flash(request, "Use a target like 01:42.018 or 1:02:03.500.", "error")
        return RedirectResponse(f"/categories/{split.category_id}", status_code=303)

    split.name = name
    split.target_ms = target_ms
    db.commit()
    flash(request, "Split updated.", "success")
    return RedirectResponse(f"/categories/{split.category_id}", status_code=303)


@app.post("/splits/{split_id}/move", name="move_split")
def move_split(
    request: Request,
    split_id: int,
    db: SessionDep,
    user: PageUser,
    direction: Annotated[int, Form()] = 0,
):
    split = owned_split(db, user, split_id)
    siblings = list(split.category.splits)
    index = next(
        (offset for offset, item in enumerate(siblings) if item.id == split.id), -1
    )
    target_index = index + direction
    if index == -1 or not 0 <= target_index < len(siblings):
        return RedirectResponse(f"/categories/{split.category_id}", status_code=303)

    other = siblings[target_index]
    split.position, other.position = other.position, split.position
    db.commit()
    return RedirectResponse(f"/categories/{split.category_id}", status_code=303)


@app.post("/splits/{split_id}/delete", name="delete_split")
def delete_split(
    request: Request,
    split_id: int,
    db: SessionDep,
    user: PageUser,
):
    split = owned_split(db, user, split_id)
    category_id = split.category_id
    name = split.name
    db.delete(split)
    db.flush()

    remaining = db.scalars(
        select(models.Split)
        .where(models.Split.category_id == category_id)
        .order_by(models.Split.position)
    ).all()
    for index, item in enumerate(remaining):
        item.position = index

    db.commit()
    flash(request, f"{name} removed from the route.", "success")
    return RedirectResponse(f"/categories/{category_id}", status_code=303)


@app.post("/runs/{run_id}/delete", name="delete_run_page")
def delete_run_page(
    request: Request,
    run_id: int,
    db: SessionDep,
    user: PageUser,
):
    run = db.get(models.Run, run_id)
    if run is None or run.category.game.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    category_id = run.category_id
    db.delete(run)
    db.commit()
    flash(request, "Run deleted from the history.", "success")
    return RedirectResponse(f"/categories/{category_id}", status_code=303)


@app.get("/categories/{category_id}/timer", name="timer_page")
def timer_page(
    request: Request,
    category_id: int,
    db: SessionDep,
    user: PageUser,
):
    category = owned_category(db, user, category_id)
    if not category.splits:
        flash(request, "Add at least one split before starting the timer.", "error")
        return RedirectResponse(f"/categories/{category.id}", status_code=303)

    timer_data = {
        "category_id": category.id,
        "category_name": category.name,
        "game_id": category.game.id,
        "game_name": category.game.name,
        "splits": [
            {"id": split.id, "name": split.name, "target_ms": split.target_ms}
            for split in category.splits
        ],
        "comparison": comparison_for(category),
        "best_segments": best_segments_for(category),
    }
    return page(
        request,
        "timer.html",
        user=user,
        category=category,
        timer_data=timer_data,
    )


@app.post(
    "/api/categories/{category_id}/send-to-pi",
    name="send_to_pi",
    response_model=schemas.Pi5QueueResponse,
)
def send_to_pi(category_id: int, db: SessionDep, user: ApiUser):
    category = owned_category(db, user, category_id)
    payload = schemas.Pi5Payload(
        category_id=category.id,
        category_name=category.name,
        game_name=category.game.name,
        splits=[
            schemas.Pi5Split(
                id=split.id,
                name=split.name,
                target_ms=split.target_ms,
            )
            for split in category.splits
        ],
    )
    logger.info("Queued category %s for Pi 5: %s", category.id, payload.model_dump())
    return schemas.Pi5QueueResponse(
        status="queued",
        message=(
            f"{category.name} queued for the Pi 5 hand-off "
            "(template transport — hardware not connected yet)."
        ),
        payload=payload,
    )


@app.post("/api/runs", name="save_run", response_model=schemas.RunSaved)
def save_run(payload: schemas.RunCreate, db: SessionDep, user: ApiUser):
    category = owned_category(db, user, payload.category_id)
    valid_split_ids = {split.id for split in category.splits}
    if not payload.splits or any(
        item.split_id not in valid_split_ids for item in payload.splits
    ):
        raise HTTPException(
            status_code=400,
            detail="The run does not match this category's split route.",
        )

    previous_best = category.personal_best
    run = models.Run(
        category_id=category.id,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        total_ms=payload.total_ms,
    )
    for item in payload.splits:
        run.splits.append(
            models.RunSplit(
                split_id=item.split_id,
                name=item.name,
                position=item.position,
                segment_ms=item.segment_ms,
                cumulative_ms=item.cumulative_ms,
            )
        )

    db.add(run)
    db.commit()
    db.refresh(run)

    is_pb = previous_best is None or run.total_ms < previous_best.total_ms
    db.expire(category, ["runs"])

    return schemas.RunSaved(
        run_id=run.id,
        total_ms=run.total_ms,
        is_pb=is_pb,
        previous_pb_ms=previous_best.total_ms if previous_best is not None else None,
        comparison=comparison_for(category),
        best_segments=best_segments_for(category),
    )


@app.delete("/api/runs/{run_id}", name="delete_run_api", status_code=204)
def delete_run_api(run_id: int, db: SessionDep, user: ApiUser):
    run = db.get(models.Run, run_id)
    if run is None or run.category.game.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    db.delete(run)
    db.commit()
    return Response(status_code=204)


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
