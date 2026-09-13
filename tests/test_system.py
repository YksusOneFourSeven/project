"""Интеграционные проверки реального FastAPI и PostgreSQL.
Запуск: docker compose exec web pytest -q --junitxml=/tmp/results.xml
Каждая изменяющая проверка удаляет созданные записи либо откатывает SQL.
"""

import os
from io import BytesIO
from uuid import uuid4
import httpx
import psycopg
import pytest
from openpyxl import load_workbook


@pytest.fixture
def client():
    with httpx.Client(base_url="http://localhost:8000", timeout=30) as c:
        yield c


@pytest.fixture
def admin(client):
    assert (
        client.post(
            "/api/login", json={"username": "admin", "password": "DemoPass123!"}
        ).status_code
        == 200
    )
    return client


def login(c, role):
    assert (
        c.post(
            "/api/login", json={"username": role, "password": "DemoPass123!"}
        ).status_code
        == 200
    )


def test_TC01_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_TC02_unauthorized(client):
    assert client.get("/api/records/students").status_code == 401


@pytest.mark.parametrize("role", ["admin", "dean", "teacher", "student"])
def test_TC03_login_roles(client, role):
    login(client, role)
    assert client.get("/api/me").json()["role"] == role
    cookie = client.cookies.get("session")
    assert len(cookie) > 30


def test_TC04_wrong_password(client):
    assert (
        client.post(
            "/api/login",
            json={"username": "nobody-" + uuid4().hex[:8], "password": "wrong"},
        ).status_code
        == 401
    )


def test_TC05_logout(admin):
    assert admin.post("/api/logout").status_code == 200
    assert admin.get("/api/me").status_code == 401


@pytest.mark.parametrize(
    "entity,n",
    [
        ("students", 20),
        ("groups", 5),
        ("disciplines", 15),
        ("teachers", 10),
        ("grades", 240),
    ],
)
def test_TC06_seed_counts(admin, entity, n):
    assert len(admin.get("/api/records/" + entity).json()) == n


# Набор включает полные CRUD-циклы каждой прикладной сущности.
SAMPLES = {
    "teachers": dict(
        full_name="Тест Тестов",
        department="Кафедра",
        position="доцент",
        degree="",
        contacts="",
    ),
    "groups": dict(
        name="TEST",
        specialty="Информатика",
        course=1,
        study_mode="очная",
        intake_year=2026,
        curator_id=1,
    ),
    "students": dict(
        full_name="Тест Студент",
        birth_date="2005-01-01",
        gender="мужской",
        contacts="",
        group_id=1,
        funding="бюджет",
        admission_date="2025-09-01",
        status="учится",
    ),
    "disciplines": dict(
        name="TEST",
        description="",
        lecture_hours=1,
        practice_hours=1,
        lab_hours=1,
        control_form="экзамен",
    ),
    "assignments": dict(
        group_id=1, discipline_id=2, teacher_id=1, semester=2, academic_year=2026
    ),
    "assessments": dict(
        assignment_id=1, title="TEST", kind="лабораторная", weight=1, grading="балл"
    ),
    "users": dict(
        username="testuser",
        password="StrongPass123!",
        role="dean",
        student_id=None,
        teacher_id=None,
        active=True,
    ),
}


@pytest.mark.parametrize("entity", list(SAMPLES))
def test_TC07_crud(admin, entity):
    payload = SAMPLES[entity].copy()
    for k in ("name", "title", "username"):
        if k in payload:
            payload[k] += uuid4().hex[:8]
    created = admin.post("/api/records/" + entity, json=payload)
    assert created.status_code == 201, created.text
    identity = created.json()["id"]
    try:
        assert any(
            x["id"] == identity for x in admin.get("/api/records/" + entity).json()
        )
        assert (
            admin.put(f"/api/records/{entity}/{identity}", json=payload).status_code
            == 200
        )
    finally:
        assert admin.delete(f"/api/records/{entity}/{identity}").status_code == 200


def test_TC08_grade_crud(admin):
    work = admin.post(
        "/api/records/assessments",
        json={**SAMPLES["assessments"], "title": uuid4().hex},
    ).json()["id"]
    try:
        payload = dict(student_id=1, assessment_id=work, value=4, comment="test")
        r = admin.post("/api/records/grades", json=payload)
        assert r.status_code == 201
        gid = r.json()["id"]
        assert (
            admin.put(
                f"/api/records/grades/{gid}", json={**payload, "value": 5}
            ).status_code
            == 200
        )
        assert admin.delete(f"/api/records/grades/{gid}").status_code == 200
    finally:
        admin.delete(f"/api/records/assessments/{work}")


def test_TC09_invalid_course(admin):
    assert (
        admin.post(
            "/api/records/groups", json={**SAMPLES["groups"], "course": 7}
        ).status_code
        == 422
    )


def test_TC10_invalid_dates(admin):
    assert (
        admin.post(
            "/api/records/students",
            json={**SAMPLES["students"], "birth_date": "2030-01-01"},
        ).status_code
        == 422
    )


def test_TC11_blank_name(admin):
    assert (
        admin.post(
            "/api/records/students", json={**SAMPLES["students"], "full_name": "  "}
        ).status_code
        == 422
    )


def test_TC12_invalid_fk(admin):
    assert (
        admin.post(
            "/api/records/students", json={**SAMPLES["students"], "group_id": 999999}
        ).status_code
        == 409
    )


def test_TC13_restrict_delete(admin):
    assert admin.delete("/api/records/groups/1").status_code == 409


def test_TC14_duplicate_grade(admin):
    assert (
        admin.post(
            "/api/records/grades", json=dict(student_id=1, assessment_id=1, value=4)
        ).status_code
        == 409
    )


def test_TC15_wrong_group_grade(admin):
    assert (
        admin.post(
            "/api/records/grades", json=dict(student_id=20, assessment_id=1, value=4)
        ).status_code
        == 409
    )


def test_TC16_invalid_scale(admin):
    row = admin.get("/api/records/grades").json()[0]
    assert (
        admin.put(
            "/api/records/grades/" + str(row.pop("id")), json={**row, "value": 1}
        ).status_code
        == 409
    )


def test_TC17_weight_zero(admin):
    assert (
        admin.post(
            "/api/records/assessments", json={**SAMPLES["assessments"], "weight": 0}
        ).status_code
        == 422
    )


def test_TC18_teacher_scope(client):
    login(client, "teacher")
    assert all(
        x["teacher_id"] == 1 for x in client.get("/api/records/assignments").json()
    )
    assert (
        client.post(
            "/api/records/assessments",
            json={**SAMPLES["assessments"], "assignment_id": 2},
        ).status_code
        == 403
    )


def test_TC19_student_privacy(client):
    login(client, "student")
    assert all(x["student_id"] == 1 for x in client.get("/api/records/grades").json())
    assert len(client.get("/api/records/students").json()) == 1
    assert client.get("/api/reports/student?student_id=2").status_code == 403


def test_TC20_student_write_denied(client):
    login(client, "student")
    assert (
        client.post(
            "/api/records/grades", json=dict(student_id=1, assessment_id=1, value=5)
        ).status_code
        == 403
    )


def test_TC21_dean_users_denied(client):
    login(client, "dean")
    assert client.get("/api/records/users").status_code == 403


def test_TC22_weighted_result(admin):
    # Независимый расчет по фиксированным данным: для студента 1 (5+3*2+4*2+5*5)/10=4.4 ->4.
    r = admin.get("/api/reports/sheet?assignment_id=1").json()
    assert r[0]["Итог"] == 4


def test_TC23_incomplete_result(admin):
    work = admin.post(
        "/api/records/assessments",
        json={**SAMPLES["assessments"], "title": uuid4().hex},
    ).json()["id"]
    try:
        assert all(
            x["Итог"] is None and x["Не завершено"]
            for x in admin.get("/api/reports/sheet?assignment_id=1").json()
        )
    finally:
        admin.delete(f"/api/records/assessments/{work}")


@pytest.mark.parametrize(
    "path",
    [
        "sheet?assignment_id=1",
        "student?student_id=1",
        "ranking?group_id=1",
        "debtors",
        "statistics",
        "quality",
    ],
)
def test_TC24_reports(admin, path):
    response = admin.get("/api/reports/" + path)
    assert response.status_code == 200, response.text
    assert len(response.json()) > 0


def test_TC25_own_rank(client):
    login(client, "student")
    r = client.get("/api/reports/ranking").json()
    assert len(r) == 1 and r[0]["ID"] == 1 and r[0]["Место"] >= 1


def test_TC26_debtors(admin):
    r = admin.get("/api/reports/debtors").json()
    assert len(r) == 15
    assert all(x["Итог"] in (0, 2) for x in r)


def test_TC27_xlsx(admin):
    r = admin.get("/api/reports/sheet?assignment_id=1&format=xlsx")
    assert r.status_code == 200
    wb = load_workbook(BytesIO(r.content))
    assert wb.active.max_row == 5


def test_TC28_pdf(admin):
    r = admin.get("/api/reports/quality?format=pdf")
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_TC29_audit(admin):
    r = admin.get("/api/records/audit_log").json()
    assert any(x["action"] == "login" for x in r)
    assert all("password" not in str(x) for x in r)


def test_TC30_backup(admin):
    r = admin.get("/api/backup")
    assert r.status_code == 200
    assert len(r.json()["students"]) == 20 and "users" not in r.json()


def test_TC31_backup_denied(client):
    login(client, "dean")
    assert client.get("/api/backup").status_code == 403


def test_TC32_self_admin_protection(admin):
    assert admin.delete("/api/records/users/1").status_code == 409


def test_TC33_bad_entity(admin):
    assert admin.get("/api/records/pg_authid").status_code == 404


def test_TC34_csrf(admin):
    assert (
        admin.post(
            "/api/logout", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_TC35_sql_injection(client):
    assert (
        client.post(
            "/api/login", json={"username": "admin' OR 1=1--", "password": "x"}
        ).status_code
        == 401
    )


def test_TC36_user_link_validation(admin):
    assert (
        admin.post(
            "/api/records/users", json={**SAMPLES["users"], "role": "student"}
        ).status_code
        == 422
    )


def test_TC37_history_protected(admin):
    row = admin.get("/api/records/students").json()[0]
    identity = row.pop("id")
    assert (
        admin.put(
            f"/api/records/students/{identity}", json={**row, "group_id": 2}
        ).status_code
        == 409
    )


def test_TC38_password_hidden(admin):
    assert all("password_hash" not in x for x in admin.get("/api/records/users").json())


def test_TC39_quality_formula(admin):
    r = admin.get("/api/reports/quality?group_id=1").json()[0]
    assert r["Студентов"] == 4 and r["На 4 и 5"] == 3 and r["Качество %"] == 75


def test_TC40_statistics_slices(admin):
    r = admin.get("/api/reports/statistics").json()
    assert {x["Срез"] for x in r} == {"группа", "курс", "специальность"}


def test_TC41_database_constraints():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE grades SET value=1 WHERE id=1")
        conn.rollback()


def test_TC42_expired_session(client):
    login(client, "student")
    from app.security import token_hash

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            "UPDATE sessions SET expires_at=now()-interval '1 second' WHERE token_hash=%s",
            (token_hash(client.cookies.get("session")),),
        )
    assert client.get("/api/me").status_code == 401


def test_TC43_teacher_report_privacy(client):
    login(client, "teacher")
    assert client.get("/api/reports/sheet?assignment_id=2").status_code == 403
    assert client.get("/api/reports/statistics").status_code == 403


def test_TC44_cookie_flags(client):
    r = client.post(
        "/api/login", json={"username": "admin", "password": "DemoPass123!"}
    )
    assert (
        "HttpOnly" in r.headers["set-cookie"]
        and "SameSite=strict" in r.headers["set-cookie"]
    )


def test_TC45_scale_change_protected(admin):
    row = admin.get("/api/records/assessments").json()[0]
    identity = row.pop("id")
    assert (
        admin.put(
            f"/api/records/assessments/{identity}", json={**row, "assignment_id": 2}
        ).status_code
        == 409
    )


def test_TC46_rate_limit(client):
    name = "unknown-" + uuid4().hex[:8]
    for _ in range(10):
        assert (
            client.post(
                "/api/login", json={"username": name, "password": "x"}
            ).status_code
            == 401
        )
    assert (
        client.post("/api/login", json={"username": name, "password": "x"}).status_code
        == 429
    )
