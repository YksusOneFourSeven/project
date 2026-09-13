/* Простой интерфейс без сборщика. Данные вставляются через textContent, а не HTML. */
const $ = (id) => document.getElementById(id);
const sections = {
  students: "Студенты",
  groups: "Группы",
  disciplines: "Дисциплины",
  teachers: "Преподаватели",
  assignments: "Назначения",
  assessments: "Контрольные работы",
  grades: "Оценки",
  reports: "Отчеты",
  users: "Пользователи",
  audit_log: "Журнал действий",
  backup: "Архив",
};
const labels = {
  id: "ID",
  full_name: "ФИО",
  birth_date: "Дата рождения",
  gender: "Пол",
  contacts: "Контакты",
  group_id: "Группа",
  funding: "Финансирование",
  admission_date: "Дата поступления",
  status: "Статус",
  name: "Название",
  specialty: "Специальность",
  course: "Курс",
  study_mode: "Форма обучения",
  intake_year: "Год набора",
  curator_id: "Куратор",
  description: "Описание",
  lecture_hours: "Лекции, ч",
  practice_hours: "Практики, ч",
  lab_hours: "Лабораторные, ч",
  control_form: "Форма контроля",
  department: "Кафедра",
  position: "Должность",
  degree: "Ученая степень",
  discipline_id: "Дисциплина",
  teacher_id: "Преподаватель",
  semester: "Семестр",
  academic_year: "Учебный год",
  assignment_id: "Назначение",
  title: "Название работы",
  kind: "Тип работы",
  weight: "Вес",
  grading: "Шкала",
  student_id: "Студент",
  assessment_id: "Работа",
  value: "Оценка",
  comment: "Комментарий",
  username: "Логин",
  password: "Пароль",
  role: "Роль",
  active: "Активен",
  user_id: "Пользователь",
  action: "Действие",
  entity: "Раздел",
  entity_id: "ID записи",
  created_at: "Дата и время",
};
const roles = {
  admin: "Администратор",
  dean: "Деканат",
  teacher: "Преподаватель",
  student: "Студент",
};
const reportNames = {
  sheet: "Ведомость по группе и дисциплине",
  student: "Сводная ведомость студента",
  ranking: "Рейтинг студентов",
  debtors: "Должники",
  statistics: "Статистика успеваемости",
  quality: "Качество знаний",
};
const refs = {
  group_id: "groups",
  curator_id: "teachers",
  teacher_id: "teachers",
  discipline_id: "disciplines",
  assignment_id: "assignments",
  assessment_id: "assessments",
  student_id: "students",
  user_id: "users",
};
let user,
  schemas,
  entity = "students",
  data = [],
  lookups = {},
  editing = null,
  sortKey = null,
  sortAsc = true;
function message(text, error = false) {
  $("message").textContent = text;
  $("message").className = error ? "error" : "";
}
// Все запросы проходят через один обработчик ошибок сервера.
async function api(path, method = "GET", body) {
  const response = await fetch("/api" + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let e = await response.json();
    throw Error(
      typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail),
    );
  }
  return response.json();
}
function guarded(fn) {
  return async (...args) => {
    try {
      await fn(...args);
    } catch (e) {
      message(e.message, true);
    }
  };
}
// Скрываем недоступные кнопки; окончательную проверку прав выполняет сервер.
function canEdit() {
  return (
    user.role === "admin" ||
    (user.role === "dean" &&
      !["users", "audit_log", "grades", "assessments"].includes(entity)) ||
    (user.role === "teacher" && ["grades", "assessments"].includes(entity))
  );
}
function refText(table, row) {
  if (!row) return "";
  if (table === "assignments")
    return `${refValue("group_id", row.group_id)} / ${refValue("discipline_id", row.discipline_id)} / ${row.academic_year}, сем. ${row.semester} [${row.id}]`;
  if (table === "assessments")
    return `${row.title} / ${refValue("assignment_id", row.assignment_id)} [${row.id}]`;
  return `${row.full_name || row.name || row.username || row.id} [${row.id}]`;
}
function refValue(key, value) {
  const table = refs[key];
  const row = (lookups[table] || []).find((x) => x.id === value);
  return row ? refText(table, row) : (value ?? "—");
}
// Загружаем справочники, чтобы показывать названия вместо числовых ID.
async function loadLookups() {
  lookups = {};
  for (const table of [
    "groups",
    "disciplines",
    "students",
    "teachers",
    "assignments",
    "assessments",
  ]) {
    if (table === "teachers" && user.role === "student") continue;
    lookups[table] = await api("/records/" + table);
  }
}
async function start() {
  user = await api("/me");
  schemas = await api("/schema");
  await loadLookups();
  $("login-panel").hidden = true;
  $("workspace").hidden = false;
  $("account").replaceChildren();
  const span = document.createElement("span");
  span.textContent = `${user.username} · ${roles[user.role]}`;
  const logout = document.createElement("button");
  logout.textContent = "Выйти";
  logout.onclick = guarded(async () => {
    await api("/logout", "POST");
    location.reload();
  });
  $("account").append(span, logout);
  const allowed =
    user.role === "student"
      ? ["grades", "reports"]
      : user.role === "teacher"
        ? [
            "students",
            "groups",
            "disciplines",
            "assignments",
            "assessments",
            "grades",
            "reports",
          ]
        : Object.keys(sections).filter(
            (x) =>
              user.role === "admin" ||
              !["users", "audit_log", "backup"].includes(x),
          );
  $("menu").replaceChildren();
  for (const key of allowed) {
    let b = document.createElement("button");
    b.textContent = sections[key];
    b.dataset.key = key;
    b.onclick = guarded(() => select(key));
    $("menu").append(b);
  }
  entity = allowed[0];
  await select(entity);
}
async function select(key) {
  entity = key;
  sortKey = null;
  $("search").value = "";
  message("");
  for (const b of $("menu").children)
    b.classList.toggle("active", b.dataset.key === key);
  $("section-title").textContent = sections[key];
  $("add").hidden =
    !canEdit() || ["reports", "audit_log", "backup"].includes(key);
  $("report-controls").hidden = key !== "reports";
  $("admin-tools").hidden = key !== "backup";
  $("toolbar").hidden = key === "backup";
  if (key === "reports") {
    await setupReports();
    data = [];
    render();
  } else if (key === "backup") {
    data = [];
    render();
  } else {
    data = await api("/records/" + key);
    render();
  }
}
function display(k, v) {
  if (refs[k]) return refValue(k, v);
  if (k === "role") return roles[v];
  return v === null ? "—" : v === true ? "да" : v === false ? "нет" : String(v);
}
// Фильтр и сортировка меняют только текущую таблицу в браузере.
function render() {
  const table = $("data-table");
  table.replaceChildren();
  let filtered = data.filter((row) =>
    Object.entries(row).some(([k, v]) =>
      display(k, v).toLowerCase().includes($("search").value.toLowerCase()),
    ),
  );
  if (sortKey)
    filtered.sort((a, b) => {
      let x = a[sortKey],
        y = b[sortKey];
      return (
        (typeof x === "number" && typeof y === "number"
          ? x - y
          : display(sortKey, x).localeCompare(display(sortKey, y), "ru", {
              numeric: true,
            })) * (sortAsc ? 1 : -1)
      );
    });
  $("count").textContent = `Записей: ${filtered.length}`;
  if (!data.length) {
    const c = table.createTBody().insertRow().insertCell();
    c.textContent =
      "Нет данных. Для отчета выберите параметры и нажмите «Сформировать».";
    return;
  }
  const keys = Object.keys(data[0]),
    head = table.createTHead().insertRow();
  for (const k of keys) {
    let th = document.createElement("th"),
      b = document.createElement("button");
    b.textContent = labels[k] || k;
    b.onclick = () => {
      sortAsc = sortKey === k ? !sortAsc : true;
      sortKey = k;
      render();
    };
    th.append(b);
    head.append(th);
  }
  const editable = canEdit() && !["reports", "audit_log"].includes(entity);
  if (editable) {
    let th = document.createElement("th");
    th.textContent = "Действия";
    head.append(th);
  }
  const body = table.createTBody();
  for (const row of filtered) {
    let tr = body.insertRow();
    for (const k of keys) tr.insertCell().textContent = display(k, row[k]);
    if (editable) {
      let cell = tr.insertCell();
      for (const [title, handler] of [
        ["Изменить", () => edit(row)],
        [
          "Удалить",
          async () => {
            if (
              confirm(
                "Удалить запись? Связанные данные могут запрещать удаление.",
              )
            ) {
              await api(`/records/${entity}/${row.id}`, "DELETE");
              await refresh();
              message("Запись удалена");
            }
          },
        ],
      ]) {
        let b = document.createElement("button");
        b.textContent = title;
        b.className = title === "Удалить" ? "danger" : "secondary";
        b.onclick = guarded(handler);
        cell.append(b);
      }
    }
  }
}
async function refresh() {
  await loadLookups();
  if (entity === "reports") await runReport();
  else await select(entity);
}
function option(select, value, text) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = text;
  select.append(o);
}
// Строим форму по JSON Schema, полученной от Pydantic на сервере.
function edit(row = null) {
  editing = row;
  $("editor-title").textContent =
    (row ? "Редактирование: " : "Добавление: ") + sections[entity];
  $("fields").replaceChildren();
  for (const [key, raw] of Object.entries(schemas[entity].properties)) {
    const rule = raw.anyOf ? raw.anyOf.find((x) => x.type !== "null") : raw;
    let label = document.createElement("label");
    label.textContent =
      (labels[key] || key) +
      (key === "password" && row ? " (пусто — не менять)" : "");
    let input;
    if (rule.enum || refs[key] || rule.type === "boolean") {
      input = document.createElement("select");
      if (raw.anyOf) option(input, "", "Не выбрано");
      if (refs[key])
        for (const item of lookups[refs[key]] || [])
          option(input, item.id, refText(refs[key], item));
      else if (rule.enum)
        for (const v of rule.enum)
          option(input, v, key === "role" ? roles[v] : v);
      else {
        option(input, "true", "Да");
        option(input, "false", "Нет");
      }
    } else {
      input = document.createElement("input");
      input.type =
        key === "password"
          ? "password"
          : rule.format === "date"
            ? "date"
            : ["integer", "number"].includes(rule.type)
              ? "number"
              : "text";
      if (rule.type === "number") input.step = "0.001";
      if (rule.minimum !== undefined) input.min = rule.minimum;
      if (rule.exclusiveMinimum !== undefined)
        input.min = rule.exclusiveMinimum + 0.001;
      if (rule.maximum !== undefined) input.max = rule.maximum;
      if (rule.maxLength) input.maxLength = rule.maxLength;
      if (rule.minLength) input.minLength = rule.minLength;
    }
    input.name = key;
    input.dataset.type = rule.type;
    input.required = (schemas[entity].required || []).includes(key);
    if (key === "password") input.required = !row;
    if (row && row[key] !== undefined && row[key] !== null)
      input.value = row[key];
    else if (raw.default !== undefined && raw.default !== null)
      input.value = raw.default;
    label.append(input);
    $("fields").append(label);
  }
  $("editor").showModal();
}
$("record-form").onsubmit = guarded(async (event) => {
  event.preventDefault();
  const body = {};
  for (const input of $("fields").querySelectorAll("input,select")) {
    let value = input.value;
    if (!value && schemas[entity].properties[input.name].anyOf) value = null;
    else if (["integer", "number"].includes(input.dataset.type))
      value = Number(value);
    else if (input.dataset.type === "boolean") value = value === "true";
    body[input.name] = value;
  }
  if (editing && !confirm("Сохранить изменения записи?")) return;
  await api(
    "/records/" + entity + (editing ? "/" + editing.id : ""),
    editing ? "PUT" : "POST",
    body,
  );
  $("editor").close();
  await refresh();
  message("Запись сохранена");
});
async function setupReports() {
  $("report-kind").replaceChildren();
  for (const [k, v] of Object.entries(reportNames))
    if (
      user.role === "admin" ||
      user.role === "dean" ||
      (user.role === "student" && ["student", "ranking"].includes(k)) ||
      (user.role === "teacher" && k === "sheet")
    )
      option($("report-kind"), k, v);
  for (const [id, table] of [
    ["report-group", "groups"],
    ["report-assignment", "assignments"],
    ["report-student", "students"],
  ]) {
    const select = $(id);
    select.replaceChildren();
    option(select, "", "Все / не выбрано");
    for (const row of lookups[table])
      option(select, row.id, refText(table, row));
  }
}
// Просмотр и экспорт используют одинаковые параметры отчета.
function reportPath(format = "json") {
  const p = new URLSearchParams({ format });
  for (const [id, key] of [
    ["report-group", "group_id"],
    ["report-assignment", "assignment_id"],
    ["report-student", "student_id"],
  ])
    if ($(id).value) p.set(key, $(id).value);
  return "/reports/" + $("report-kind").value + "?" + p;
}
async function runReport() {
  data = await api(reportPath());
  $("section-title").textContent = reportNames[$("report-kind").value];
  render();
  message("Отчет сформирован");
}
// Создаем временную ссылку для скачивания и затем освобождаем ее.
async function download(path, name) {
  const r = await fetch("/api" + path);
  if (!r.ok) {
    const e = await r.json();
    throw Error(e.detail);
  }
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("login").onsubmit = guarded(async (e) => {
  e.preventDefault();
  await api("/login", "POST", Object.fromEntries(new FormData(e.target)));
  message("");
  await start();
});
$("search").oninput = render;
$("add").onclick = () => edit();
$("cancel").onclick = () => $("editor").close();
$("refresh").onclick = guarded(refresh);
$("run-report").onclick = guarded(runReport);
$("excel").onclick = guarded(() => download(reportPath("xlsx"), "report.xlsx"));
$("pdf").onclick = guarded(() => download(reportPath("pdf"), "report.pdf"));
$("print").onclick = () => window.print();
$("backup").onclick = guarded(() => download("/backup", "academic-data.json"));
start().catch(() => {
  $("workspace").hidden = true;
  $("login-panel").hidden = false;
});
