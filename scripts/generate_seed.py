"""Создает воспроизводимый DML с синтетическими учебными данными."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security import hash_password

sql = [
    "-- DML: все люди и контакты вымышлены. Пароль демонстрационных записей: DemoPass123!\nBEGIN;"
]


def insert(table, rows):
    def value(x):
        if x is None:
            return "NULL"
        if isinstance(x, (int, float)):
            return str(x)
        return "'" + str(x).replace("'", "''") + "'"

    for row in rows:
        sql.append(f"INSERT INTO {table} VALUES ({','.join(map(value,row))});")


insert(
    "teachers",
    [
        (
            i,
            f"Преподаватель {i} Иван Иванович",
            "Информатики",
            "доцент",
            "кандидат наук",
            f"teacher{i}@example.test",
        )
        for i in range(1, 11)
    ],
)
insert(
    "groups",
    [
        (
            i,
            f"ИС-{i}01",
            "Информационные системы" if i < 4 else "Прикладная информатика",
            i,
            "очная",
            2027 - i,
            i,
        )
        for i in range(1, 6)
    ],
)
names = [
    "Иванов Иван Иванович",
    "Петров Петр Петрович",
    "Сидорова Анна Сергеевна",
    "Смирнова Мария Олеговна",
]
insert(
    "students",
    [
        (
            i,
            names[(i - 1) % 4] + f" {i}",
            "2005-03-15",
            "мужской" if (i - 1) % 4 < 2 else "женский",
            f"student{i}@example.test",
            (i - 1) // 4 + 1,
            "бюджет" if i % 2 else "контракт",
            "2022-09-01",
            "учится",
        )
        for i in range(1, 21)
    ],
)
names = [
    "Математика",
    "Информатика",
    "Программирование",
    "Базы данных",
    "Физика",
    "История",
    "Английский язык",
    "Философия",
    "Сети",
    "Операционные системы",
    "Алгоритмы",
    "Веб-разработка",
    "Безопасность",
    "Экономика",
    "Проектирование ИС",
]
insert(
    "disciplines",
    [
        (
            i,
            names[i - 1],
            "Учебная дисциплина",
            32,
            16,
            16,
            "зачет" if i % 5 == 0 else "экзамен",
        )
        for i in range(1, 16)
    ],
)
insert(
    "assignments",
    [(i, (i - 1) // 3 + 1, i, (i - 1) % 10 + 1, 1, 2026) for i in range(1, 16)],
)
insert(
    "assessments",
    [
        (
            i,
            (i - 1) // 4 + 1,
            ["Лабораторная 1", "Контрольная", "Курсовая", "Итог семестра"][(i - 1) % 4],
            ["лабораторная", "контрольная", "курсовая", "семестровая"][(i - 1) % 4],
            [1, 2, 2, 5][(i - 1) % 4],
            "зачет" if ((i - 1) // 4 + 1) % 5 == 0 else "балл",
        )
        for i in range(1, 61)
    ],
)
rows = []
for a in range(1, 61):
    assignment = (a - 1) // 4 + 1
    group = (assignment - 1) // 3 + 1
    for s in range((group - 1) * 4 + 1, group * 4 + 1):
        v = (
            (0 if s % 4 == 0 else 1)
            if assignment % 5 == 0
            else (2 if s % 4 == 0 else 3 + (s + a) % 3)
        )
        rows.append((len(rows) + 1, s, a, v, ""))
insert("grades", rows)
insert(
    "users",
    [
        (1, "admin", hash_password("DemoPass123!"), "admin", None, None, True),
        (2, "dean", hash_password("DemoPass123!"), "dean", None, None, True),
        (3, "teacher", hash_password("DemoPass123!"), "teacher", None, 1, True),
        (4, "student", hash_password("DemoPass123!"), "student", 1, None, True),
    ],
)
for table in [
    "teachers",
    "groups",
    "students",
    "disciplines",
    "assignments",
    "assessments",
    "grades",
    "users",
]:
    sql.append(
        f"SELECT setval(pg_get_serial_sequence('{table}','id'),(SELECT max(id) FROM {table}));"
    )
sql.append("COMMIT;")
Path("sql/02_seed.sql").write_text("\n".join(sql), encoding="utf-8")
