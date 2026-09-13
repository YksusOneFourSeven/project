"""HTTP-слой: сессии, API, экспорт и статический интерфейс."""

import os
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dishka import make_async_container
from dishka.integrations.fastapi import DishkaRoute, FromDishka, setup_dishka
from psycopg import AsyncConnection, IntegrityError
from app.db import DatabaseProvider, one, rows
from app.security import token_hash, verify_password, hash_password
from app.schemas import Login, SCHEMAS
from app.service import list_records, mutate, audit, allow
from app.reports import report, export_xlsx, export_pdf, TITLES


@asynccontextmanager
async def lifespan(app):
    yield
    await app.state.dishka_container.close()


app = FastAPI(title="Учет успеваемости студентов", version="1.0.0", lifespan=lifespan, redoc_url=None)
setup_dishka(make_async_container(DatabaseProvider()), app)
router = APIRouter(prefix="/api", route_class=DishkaRoute)
DUMMY_HASH = hash_password("timing-placeholder-password")


@app.exception_handler(IntegrityError)
async def integrity_handler(request, exc):
    # Не раскрываем SQL, имена ограничений и внутренние сведения пользователю.
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Операция нарушает целостность данных: дубликат, связанные записи или несовместимые значения."
        },
    )


@app.middleware("http")
async def security_headers(request, call_next):
    # Cookie не отправляется с чужого сайта; дополнительно проверяем Origin мутаций.
    if request.method in ("POST", "PUT", "DELETE"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse(
                status_code=403, content={"detail": "Недопустимый источник запроса"}
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # Swagger использует CDN и встроенный скрипт инициализации.
    # Исключение действует только на страницу документации, интерфейс остается строгим.
    if request.url.path == "/docs":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        )
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


async def current(conn, request):
    token = request.cookies.get("session", "")
    user = await one(
        conn,
        "SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=%s AND s.expires_at>now() AND u.active",
        (token_hash(token),),
    )
    if not user:
        raise HTTPException(401, "Войдите в систему")
    return user


@router.post("/login")
async def login(
    data: Login, request: Request, response: Response, conn: FromDishka[AsyncConnection]
):
    # Ограничитель сохраняется в БД, поэтому перезапуск web не сбрасывает счетчик.
    key = token_hash(
        (request.client.host if request.client else "local") + ":" + data.username
    )
    await conn.execute(
        "DELETE FROM login_attempts WHERE attempted_at<now()-interval '15 minutes'"
    )
    count = await one(
        conn, "SELECT count(*) n FROM login_attempts WHERE key=%s", (key,)
    )
    if count["n"] >= 10:
        raise HTTPException(429, "Слишком много попыток. Повторите через 15 минут")
    user = await one(conn, "SELECT * FROM users WHERE username=%s", (data.username,))
    valid = verify_password(
        data.password, user["password_hash"] if user else DUMMY_HASH
    )
    if not user or not user["active"] or not valid:
        await conn.execute("INSERT INTO login_attempts(key) VALUES(%s)", (key,))
        await conn.commit()  # Неуспешный вход тоже должен сохраниться при HTTP 401.
        raise HTTPException(401, "Неверный логин или пароль")
    await conn.execute("DELETE FROM login_attempts WHERE key=%s", (key,))
    await conn.execute(
        "DELETE FROM sessions WHERE expires_at<=now() OR token_hash=%s",
        (token_hash(request.cookies.get("session", "")),),
    )
    token = secrets.token_urlsafe(32)
    await conn.execute(
        "INSERT INTO sessions(token_hash,user_id) VALUES(%s,%s)",
        (token_hash(token), user["id"]),
    )
    response.set_cookie(
        "session",
        token,
        httponly=True,
        samesite="strict",
        secure=os.getenv("COOKIE_SECURE") == "true",
        max_age=28800,
    )
    await audit(conn, user, "login", "users", user["id"])
    return {"username": user["username"], "role": user["role"]}


@router.post("/logout")
async def logout(
    request: Request, response: Response, conn: FromDishka[AsyncConnection]
):
    user = await current(conn, request)
    await conn.execute(
        "DELETE FROM sessions WHERE token_hash=%s",
        (token_hash(request.cookies.get("session", "")),),
    )
    response.delete_cookie("session")
    await audit(conn, user, "logout", "users", user["id"])
    return {"ok": True}


@router.get("/me")
async def me(request: Request, conn: FromDishka[AsyncConnection]):
    user = await current(conn, request)
    return {k: user[k] for k in ("id", "username", "role", "student_id", "teacher_id")}


@router.get("/schema")
async def schema(request: Request, conn: FromDishka[AsyncConnection]):
    await current(conn, request)
    return {k: v.model_json_schema() for k, v in SCHEMAS.items()}


@router.get("/records/{entity}")
async def records(entity: str, request: Request, conn: FromDishka[AsyncConnection]):
    return await list_records(conn, await current(conn, request), entity)


@router.post("/records/{entity}", status_code=201)
async def create(
    entity: str, data: dict, request: Request, conn: FromDishka[AsyncConnection]
):
    return await mutate(conn, await current(conn, request), entity, data)


@router.put("/records/{entity}/{identity}")
async def update(
    entity: str,
    identity: int,
    data: dict,
    request: Request,
    conn: FromDishka[AsyncConnection],
):
    return await mutate(conn, await current(conn, request), entity, data, identity)


@router.delete("/records/{entity}/{identity}")
async def delete(
    entity: str, identity: int, request: Request, conn: FromDishka[AsyncConnection]
):
    return await mutate(conn, await current(conn, request), entity, {}, identity, True)


@router.get("/reports/{kind}")
async def reports(
    kind: str,
    request: Request,
    conn: FromDishka[AsyncConnection],
    group_id: int | None = None,
    assignment_id: int | None = None,
    student_id: int | None = None,
    format: str = "json",
):
    user = await current(conn, request)
    data = await report(conn, user, kind, group_id, assignment_id, student_id)
    if format == "json":
        return data
    if format not in ("xlsx", "pdf"):
        raise HTTPException(422, "Допустимые форматы: json, xlsx, pdf")
    await audit(conn, user, "export", kind)
    payload = export_xlsx(data) if format == "xlsx" else export_pdf(data, TITLES[kind])
    mime = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if format == "xlsx"
        else "application/pdf"
    )
    return Response(
        payload,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{kind}.{format}"'},
    )


@router.get("/backup")
async def backup(request: Request, conn: FromDishka[AsyncConnection]):
    user = await current(conn, request)
    allow(user, "admin")
    await audit(conn, user, "backup", "database")
    # Один SQL-запрос дает согласованный снимок прикладных таблиц.
    # Пароли и сессии не включаем в доступную из браузера архивную выгрузку.
    from fastapi.encoders import jsonable_encoder
    import json

    names = [x for x in SCHEMAS if x != "users"]
    query = "SELECT " + ",".join(
        f"(SELECT coalesce(json_agg(t),'[]') FROM {t} t) AS {t}" for t in names
    )
    data = await one(conn, query)
    return Response(
        json.dumps(jsonable_encoder(data), ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="academic-data.json"'},
    )


@app.get("/health")
async def health():
    async with app.state.dishka_container() as scope:
        conn = await scope.get(AsyncConnection)
        await conn.execute("SELECT 1")
    return {"status": "ok"}


app.include_router(router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def index():
    return FileResponse("app/static/index.html")
