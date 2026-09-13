"""Явные схемы полей: неизвестные поля отклоняются, строки обрезаются по краям."""

from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


Name = str


class Teacher(Record):
    full_name: str = Field(min_length=1, max_length=150)
    department: str = Field(min_length=1, max_length=150)
    position: str = Field(min_length=1, max_length=100)
    degree: str = Field(max_length=100)
    contacts: str = Field(max_length=200)


class Group(Record):
    name: str = Field(min_length=1, max_length=40)
    specialty: str = Field(min_length=1, max_length=150)
    course: int = Field(ge=1, le=6)
    study_mode: Literal["очная", "заочная", "очно-заочная"]
    intake_year: int = Field(ge=2000, le=2100)
    curator_id: int | None = Field(default=None, gt=0)


class Student(Record):
    full_name: str = Field(min_length=1, max_length=150)
    birth_date: date
    gender: Literal["мужской", "женский"]
    contacts: str = Field(max_length=200)
    group_id: int = Field(gt=0)
    funding: Literal["бюджет", "контракт"]
    admission_date: date
    status: Literal["учится", "академический отпуск", "отчислен"]

    @model_validator(mode="after")
    def dates(self):
        if (
            not date(1900, 1, 1)
            <= self.birth_date
            < self.admission_date
            <= date.today()
        ):
            raise ValueError("Проверьте дату рождения и дату поступления")
        return self


class Discipline(Record):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(max_length=2000)
    lecture_hours: int = Field(ge=0, le=1000)
    practice_hours: int = Field(ge=0, le=1000)
    lab_hours: int = Field(ge=0, le=1000)
    control_form: Literal["экзамен", "зачет", "курсовая"]


class Assignment(Record):
    group_id: int = Field(gt=0)
    discipline_id: int = Field(gt=0)
    teacher_id: int = Field(gt=0)
    semester: int = Field(ge=1, le=12)
    academic_year: int = Field(ge=2000, le=2100)


class Assessment(Record):
    assignment_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=150)
    kind: Literal["лабораторная", "контрольная", "курсовая", "семестровая"]
    weight: float = Field(gt=0, le=100)
    grading: Literal["балл", "зачет"]


class Grade(Record):
    student_id: int = Field(gt=0)
    assessment_id: int = Field(gt=0)
    value: int = Field(ge=0, le=5)
    comment: str = Field(default="", max_length=300)


class User(Record):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str | None = Field(default=None, min_length=10, max_length=128)
    role: Literal["admin", "dean", "teacher", "student"]
    student_id: int | None = Field(default=None, gt=0)
    teacher_id: int | None = Field(default=None, gt=0)
    active: bool = True

    @model_validator(mode="after")
    def role_link(self):
        valid = (
            (self.role == "student" and self.student_id and not self.teacher_id)
            or (self.role == "teacher" and self.teacher_id and not self.student_id)
            or (
                self.role in ("admin", "dean")
                and not self.student_id
                and not self.teacher_id
            )
        )
        if not valid:
            raise ValueError(
                "Роль должна соответствовать привязке к студенту или преподавателю"
            )
        return self


class Login(Record):
    username: str = Field(max_length=50)
    password: str = Field(max_length=128)


SCHEMAS = dict(
    teachers=Teacher,
    groups=Group,
    students=Student,
    disciplines=Discipline,
    assignments=Assignment,
    assessments=Assessment,
    grades=Grade,
    users=User,
)
