"""Разграничение прав и CRUD. Имена таблиц берутся только из белого списка."""

from fastapi import HTTPException
from psycopg import sql
from pydantic import ValidationError
from app.schemas import SCHEMAS
from app.security import hash_password
from app.db import rows, one


async def audit(conn, user, action, entity, identity=None):
    await conn.execute(
        "INSERT INTO audit_log(user_id,action,entity,entity_id) VALUES(%s,%s,%s,%s)",
        (user["id"], action, entity, identity),
    )


def allow(user, *roles):
    if user["role"] not in roles:
        raise HTTPException(403, "Недостаточно прав")


async def assignment_access(conn, user, aid):
    a = await one(conn, "SELECT * FROM assignments WHERE id=%s", (aid,))
    if not a:
        raise HTTPException(422, "Назначение не найдено")
    if user["role"] == "teacher" and a["teacher_id"] != user["teacher_id"]:
        raise HTTPException(403, "Это дисциплина другого преподавателя")
    return a


async def list_records(conn, user, entity):
    if entity not in SCHEMAS and entity != "audit_log":
        raise HTTPException(404, "Раздел не найден")
    role = user["role"]
    if entity in ("users", "audit_log"):
        allow(user, "admin")
    if entity == "audit_log":
        return await rows(conn, "SELECT * FROM audit_log ORDER BY id DESC LIMIT 500")
    if role == "student":
        if entity == "students":
            return await rows(
                conn, "SELECT * FROM students WHERE id=%s", (user["student_id"],)
            )
        if entity == "grades":
            return await rows(
                conn,
                "SELECT * FROM grades WHERE student_id=%s ORDER BY id",
                (user["student_id"],),
            )
        if entity == "groups":
            return await rows(
                conn,
                "SELECT g.* FROM groups g JOIN students s ON s.group_id=g.id WHERE s.id=%s",
                (user["student_id"],),
            )
        if entity == "assignments":
            return await rows(
                conn,
                "SELECT a.* FROM assignments a JOIN students s ON s.group_id=a.group_id WHERE s.id=%s",
                (user["student_id"],),
            )
        if entity == "assessments":
            return await rows(
                conn,
                "SELECT t.* FROM assessments t JOIN assignments a ON a.id=t.assignment_id JOIN students s ON s.group_id=a.group_id WHERE s.id=%s",
                (user["student_id"],),
            )
        if entity == "teachers":
            raise HTTPException(403, "Раздел недоступен")
    if role == "teacher":
        if entity == "students":
            return await rows(
                conn,
                "SELECT s.* FROM students s WHERE group_id IN (SELECT group_id FROM assignments WHERE teacher_id=%s)",
                (user["teacher_id"],),
            )
        if entity == "groups":
            return await rows(
                conn,
                "SELECT * FROM groups WHERE id IN (SELECT group_id FROM assignments WHERE teacher_id=%s)",
                (user["teacher_id"],),
            )
        if entity == "assignments":
            return await rows(
                conn,
                "SELECT * FROM assignments WHERE teacher_id=%s",
                (user["teacher_id"],),
            )
        if entity == "assessments":
            return await rows(
                conn,
                "SELECT t.* FROM assessments t JOIN assignments a ON a.id=t.assignment_id WHERE a.teacher_id=%s",
                (user["teacher_id"],),
            )
        if entity == "grades":
            return await rows(
                conn,
                "SELECT g.* FROM grades g JOIN assessments t ON t.id=g.assessment_id JOIN assignments a ON a.id=t.assignment_id WHERE a.teacher_id=%s",
                (user["teacher_id"],),
            )
        if entity == "teachers":
            return await rows(
                conn, "SELECT * FROM teachers WHERE id=%s", (user["teacher_id"],)
            )
    fields = (
        sql.SQL("id,username,role,student_id,teacher_id,active")
        if entity == "users"
        else sql.SQL("*")
    )
    return await rows(
        conn,
        sql.SQL("SELECT {} FROM {} ORDER BY id").format(fields, sql.Identifier(entity)),
    )


async def mutate(conn, user, entity, data, identity=None, delete=False):
    if entity not in SCHEMAS:
        raise HTTPException(404, "Раздел не найден")
    allow(user, "admin", "teacher" if entity in ("grades", "assessments") else "dean")
    if entity == "users":
        allow(user, "admin")
    old = None
    if identity:
        old = await one(
            conn,
            sql.SQL("SELECT * FROM {} WHERE id=%s FOR UPDATE").format(
                sql.Identifier(entity)
            ),
            (identity,),
        )
        if not old:
            raise HTTPException(404, "Запись не найдена")
    if not delete:
        try:
            clean = SCHEMAS[entity].model_validate(data).model_dump()
        except ValidationError as e:
            raise HTTPException(
                422,
                "; ".join(
                    f"{'.'.join(map(str,x['loc']))}: {x['msg']}" for x in e.errors()
                ),
            )
    else:
        clean = old
    # Проверяем и старую, и новую привязку, чтобы нельзя было захватить чужую запись.
    for record in [x for x in (old, clean) if x]:
        if entity == "grades":
            t = await one(
                conn,
                "SELECT * FROM assessments WHERE id=%s",
                (record["assessment_id"],),
            )
            if not t:
                raise HTTPException(422, "Контрольная работа не найдена")
            await assignment_access(conn, user, t["assignment_id"])
        elif entity == "assessments":
            a = await assignment_access(conn, user, record["assignment_id"])
            d = await one(
                conn,
                "SELECT control_form FROM disciplines WHERE id=%s",
                (a["discipline_id"],),
            )
            if (record["grading"] == "зачет") != (d["control_form"] == "зачет"):
                raise HTTPException(
                    422, "Шкала работы должна соответствовать форме контроля дисциплины"
                )
    if old and not delete:
        if entity == "assignments" and any(
            clean[k] != old[k] for k in ("group_id", "discipline_id")
        ):
            if await one(
                conn,
                "SELECT id FROM assessments WHERE assignment_id=%s LIMIT 1",
                (identity,),
            ):
                raise HTTPException(409, "Назначение уже содержит работы")
        if entity == "assessments" and any(
            clean[k] != old[k] for k in ("assignment_id", "grading")
        ):
            if await one(
                conn,
                "SELECT id FROM grades WHERE assessment_id=%s LIMIT 1",
                (identity,),
            ):
                raise HTTPException(409, "Работа уже содержит оценки")
        if entity == "disciplines" and clean["control_form"] != old["control_form"]:
            if await one(
                conn,
                "SELECT id FROM assignments WHERE discipline_id=%s LIMIT 1",
                (identity,),
            ):
                raise HTTPException(409, "Дисциплина уже назначена группе")
    if entity == "users":
        if identity == user["id"] and (
            delete or not clean["active"] or clean["role"] != "admin"
        ):
            raise HTTPException(
                409, "Нельзя удалить, отключить или понизить собственную учетную запись"
            )
        if not delete:
            password = clean.pop("password")
            if not identity and not password:
                raise HTTPException(422, "Укажите пароль длиной не менее 10 символов")
            if password:
                clean["password_hash"] = hash_password(password)
            if identity:
                await conn.execute("DELETE FROM sessions WHERE user_id=%s", (identity,))
    table = sql.Identifier(entity)
    if delete:
        await conn.execute(
            sql.SQL("DELETE FROM {} WHERE id=%s").format(table), (identity,)
        )
        result = {"id": identity}
    elif identity:
        parts = sql.SQL(",").join(
            sql.SQL("{}=%s").format(sql.Identifier(k)) for k in clean
        )
        result = await one(
            conn,
            sql.SQL("UPDATE {} SET {} WHERE id=%s RETURNING id").format(table, parts),
            (*clean.values(), identity),
        )
    else:
        fields = sql.SQL(",").join(map(sql.Identifier, clean))
        placeholders = sql.SQL(",").join(sql.Placeholder() for _ in clean)
        result = await one(
            conn,
            sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
                table, fields, placeholders
            ),
            tuple(clean.values()),
        )
    await audit(
        conn,
        user,
        "delete" if delete else "update" if identity else "create",
        entity,
        result["id"],
    )
    return result
