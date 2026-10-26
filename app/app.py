"""Streamlit-приложение «Система управления менеджерами».

Архитектура:
    * Слой данных (DB Layer)  — подключение к PostgreSQL и SQL-запросы.
    * Слой сервисов (Services) — бизнес-логика (аутентификация, задачи, клиенты).
    * Слой представления (UI)  — страницы Streamlit для ролей admin/manager.

Данные хранятся в двух базах PostgreSQL: ``managers`` (сотрудники, пользователи,
задачи) и ``clients`` (клиенты компании). Настройки берутся из переменных
окружения: DB_HOST, DB_USER, DB_PASSWORD, MANAGERS_DB, CLIENTS_DB.
"""

import hashlib
import os
from contextlib import contextmanager
from datetime import datetime

import psycopg2
import streamlit as st
from psycopg2 import Error as Psycopg2Error
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")
MANAGERS_DB = os.getenv("MANAGERS_DB", "managers")
CLIENTS_DB = os.getenv("CLIENTS_DB", "clients")

TASK_STATUSES = ["Новая", "В работе", "Завершена"]
USER_ROLES = ["admin", "manager"]


# ===========================================================================
# Слой данных (DB Layer)
# ===========================================================================
@contextmanager
def get_db_connection(db_name):
    """Открыть соединение с PostgreSQL и гарантированно закрыть его."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=db_name,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        yield conn
    finally:
        if conn is not None:
            conn.close()


def run_query(db_name, query, params=None, fetch="all"):
    """Выполнить один SQL-запрос и вернуть строки в виде словарей.

    :param fetch: ``"all"`` — все строки, ``"one"`` — одна строка,
                  ``None`` — без выборки (INSERT/UPDATE/DDL, авто-commit).
    """
    with get_db_connection(db_name) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            if fetch == "all":
                return cur.fetchall()
            if fetch == "one":
                return cur.fetchone()
            conn.commit()
            return None


# ---------------------------------- DDL -----------------------------------
SCHEMA_MANAGERS = """
CREATE TABLE IF NOT EXISTS managers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    department TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    manager_id INTEGER REFERENCES managers(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    client_id INTEGER NOT NULL,
    assigned_to INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_by INTEGER REFERENCES users(id) ON DELETE CASCADE,
    deadline DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'Новая',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_CLIENTS = """
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_person TEXT,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    manager_id INTEGER,
    comments TEXT
);
"""


def init_dbs():
    """Создать таблицы в обеих базах, если их ещё нет."""
    try:
        run_query(MANAGERS_DB, SCHEMA_MANAGERS, fetch=None)
        run_query(CLIENTS_DB, SCHEMA_CLIENTS, fetch=None)
    except Psycopg2Error as exc:
        st.error(f"Ошибка инициализации БД: {exc}")


# ============================== Менеджеры =================================
def add_manager(name, email, phone, department):
    """Добавить менеджера. Вернуть True при успехе, False при дубликате email."""
    try:
        run_query(
            MANAGERS_DB,
            "INSERT INTO managers (name, email, phone, department) "
            "VALUES (%s, %s, %s, %s)",
            (name, email, phone, department),
            fetch=None,
        )
        return True
    except Psycopg2Error:
        return False


def get_all_managers():
    return run_query(
        MANAGERS_DB,
        "SELECT id, name, email, phone, department FROM managers ORDER BY id",
    )


def _get_manager_names_map():
    """Словарь «id менеджера -> ФИО» (для обогащения клиентов из другой БД)."""
    return {row["id"]: row["name"] for row in get_all_managers()}


def get_departments():
    rows = run_query(
        MANAGERS_DB,
        "SELECT DISTINCT department FROM managers "
        "WHERE department IS NOT NULL ORDER BY department",
    )
    return [row["department"] for row in rows]


def get_managers_for_assignment():
    """Словарь «ФИО менеджера -> id пользователя» для назначений задач."""
    rows = run_query(
        MANAGERS_DB,
        """
        SELECT m.name AS name, u.id AS user_id
        FROM users u
        JOIN managers m ON u.manager_id = m.id
        WHERE u.role = 'manager'
        """,
    )
    return {row["name"]: row["user_id"] for row in rows}


# ================================ Клиенты =================================
def add_client(company_name, contact_person, email, phone, manager_id=None):
    """Добавить клиента. Вернуть True при успехе, False при дубликате email."""
    try:
        run_query(
            CLIENTS_DB,
            "INSERT INTO clients (company_name, contact_person, email, "
            "phone, manager_id) VALUES (%s, %s, %s, %s, %s)",
            (company_name, contact_person, email, phone, manager_id),
            fetch=None,
        )
        return True
    except Psycopg2Error:
        return False


def get_all_clients():
    """Клиенты с именем закреплённого менеджера (связь через базы БД)."""
    clients = run_query(
        CLIENTS_DB,
        "SELECT id, company_name, contact_person, email, phone, manager_id "
        "FROM clients ORDER BY id",
    )
    manager_names = _get_manager_names_map()
    for client in clients:
        client["manager_name"] = manager_names.get(client["manager_id"])
    return clients


def get_client_by_id(client_id):
    return run_query(
        CLIENTS_DB,
        "SELECT id, company_name, contact_person, email, phone, manager_id, "
        "comments FROM clients WHERE id = %s",
        (client_id,),
        fetch="one",
    )


def get_clients_for_task():
    """Словарь «название компании -> id» для выпадающих списков."""
    rows = run_query(
        CLIENTS_DB,
        "SELECT id, company_name FROM clients ORDER BY company_name",
    )
    return {row["company_name"]: row["id"] for row in rows}


def add_comment_to_client(client_id, comment, user_name):
    """Добавить комментарий с меткой времени в начало истории клиента."""
    client = get_client_by_id(client_id)
    if client is None:
        return
    existing = client["comments"] or ""
    new_line = (
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} - {user_name}: {comment}"
    )
    updated = f"{new_line}\n{existing}".strip()
    run_query(
        CLIENTS_DB,
        "UPDATE clients SET comments = %s WHERE id = %s",
        (updated, client_id),
        fetch=None,
    )


# =============================== Пользователи =============================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate(username, password):
    """Проверить учётные данные; вернуть dict или None."""
    try:
        return run_query(
            MANAGERS_DB,
            """
            SELECT u.id, u.role, u.manager_id, m.name AS manager_name
            FROM users u
            LEFT JOIN managers m ON u.manager_id = m.id
            WHERE u.username = %s AND u.password = %s
            """,
            (username, hash_password(password)),
            fetch="one",
        )
    except Psycopg2Error as exc:
        st.error(f"Ошибка аутентификации: {exc}")
        return None


def create_user(username, password, role, manager_id=None):
    """Создать пользователя. Вернуть False, если логин уже занят."""
    try:
        run_query(
            MANAGERS_DB,
            "INSERT INTO users (username, password, role, manager_id) "
            "VALUES (%s, %s, %s, %s)",
            (username, hash_password(password), role, manager_id),
            fetch=None,
        )
        return True
    except Psycopg2Error:
        return False


def get_all_users():
    return run_query(
        MANAGERS_DB,
        """
        SELECT u.id, u.username, u.role, m.name AS manager_name
        FROM users u
        LEFT JOIN managers m ON u.manager_id = m.id
        ORDER BY u.id
        """,
    )


def create_first_admin():
    """Если таблица users пуста — создать администратора admin/admin123."""
    try:
        row = run_query(
            MANAGERS_DB, "SELECT COUNT(*) AS cnt FROM users", fetch="one"
        )
        if row and row["cnt"] == 0:
            run_query(
                MANAGERS_DB,
                "INSERT INTO users (username, password, role) "
                "VALUES (%s, %s, %s)",
                ("admin", hash_password("admin123"), "admin"),
                fetch=None,
            )
    except Psycopg2Error as exc:
        st.error(f"Ошибка создания первого администратора: {exc}")


# ================================== Задачи ================================
def create_task(title, description, client_id, assigned_to, created_by,
                deadline):
    try:
        run_query(
            MANAGERS_DB,
            """
            INSERT INTO tasks
                (title, description, client_id, assigned_to, created_by,
                 deadline)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (title, description, client_id, assigned_to, created_by, deadline),
            fetch=None,
        )
        return True
    except Psycopg2Error as exc:
        st.error(f"Ошибка создания задачи: {exc}")
        return False


def get_tasks_by_user(user_id):
    """Задачи пользователя; название клиента подтягивается из базы clients."""
    tasks = run_query(
        MANAGERS_DB,
        """
        SELECT t.id, t.title, t.description, t.client_id,
               t.deadline, t.status, t.created_at
        FROM tasks t
        WHERE t.assigned_to = %s
        ORDER BY t.deadline
        """,
        (user_id,),
    )
    companies = get_clients_for_task()  # {company_name: client_id}
    name_by_id = {cid: cname for cname, cid in companies.items()}
    for task in tasks:
        task["company_name"] = name_by_id.get(task["client_id"])
    return tasks


def get_all_tasks():
    """Все задачи с именами менеджеров и клиентов (через обе базы БД)."""
    tasks = run_query(
        MANAGERS_DB,
        """
        SELECT t.id, t.title, m.name AS manager_name, t.client_id,
               t.deadline, t.status, t.created_at
        FROM tasks t
        JOIN users u ON t.assigned_to = u.id
        JOIN managers m ON u.manager_id = m.id
        ORDER BY t.deadline
        """,
    )
    companies = get_clients_for_task()
    name_by_id = {cid: cname for cname, cid in companies.items()}
    for task in tasks:
        task["company_name"] = name_by_id.get(task["client_id"])
    return tasks


def update_task_status(task_id, status):
    run_query(
        MANAGERS_DB,
        "UPDATE tasks SET status = %s WHERE id = %s",
        (status, task_id),
        fetch=None,
    )


def get_manager_tasks_dashboard():
    """Агрегаты для админского дашборда: статусы, менеджеры, просрочки."""
    status_rows = run_query(
        MANAGERS_DB,
        "SELECT status, COUNT(*) AS cnt FROM tasks GROUP BY status",
    )
    manager_rows = run_query(
        MANAGERS_DB,
        """
        SELECT m.name, COUNT(t.id) AS cnt
        FROM tasks t
        JOIN users u ON t.assigned_to = u.id
        JOIN managers m ON u.manager_id = m.id
        GROUP BY m.name
        """,
    )
    overdue_row = run_query(
        MANAGERS_DB,
        """
        SELECT COUNT(*) AS cnt FROM tasks
        WHERE deadline < CURRENT_DATE AND status != 'Завершена'
        """,
        fetch="one",
    )
    return {
        "status_counts": {r["status"]: r["cnt"] for r in status_rows},
        "manager_counts": {r["name"]: r["cnt"] for r in manager_rows},
        "overdue_count": overdue_row["cnt"] if overdue_row else 0,
    }


# ===========================================================================
# Слой представления (Streamlit UI)
# ===========================================================================
ADMIN_MENU = [
    "👥 Пользователи",
    "📋 Задачи: Создать",
    "📊 Задачи: Дашборд",
    "👔 Менеджеры: Добавить",
    "📋 Менеджеры: Просмотр",
    "🏭 Клиенты: Просмотр",
]
MANAGER_MENU = [
    "📋 Мои задачи",
    "🏭 Клиенты: Задачи",
]


def rerun():
    """Совместимый перезапуск приложения для разных версий Streamlit."""
    if hasattr(st, "rerun"):
        st.rerun()
    else:  # pragma: no cover - fallback для старых версий
        st.experimental_rerun()


def init_session_state():
    defaults = {
        "authenticated": False,
        "user_id": None,
        "role": None,
        "manager_id": None,
        "manager_name": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def logout():
    init_session_state()


# ------------------------------- Страницы: Admin --------------------------
def page_users():
    st.subheader("👥 Управление пользователями")

    with st.expander("➕ Создать нового пользователя"):
        with st.form("create_user_form"):
            username = st.text_input("Логин*")
            password = st.text_input("Пароль*", type="password")
            role = st.selectbox("Роль*", USER_ROLES)
            managers = get_managers_for_assignment()
            manager = st.selectbox("Менеджер", [""] + list(managers.keys()))
            submit = st.form_submit_button("💾 Создать")

        if submit:
            if not all([username, password, role]):
                st.error("🚨 Обязательные поля отмечены звездочкой*")
            elif create_user(
                username, password, role, managers.get(manager) or None
            ):
                st.success("✅ Пользователь успешно создан!")
                rerun()
            else:
                st.error("⛔ Ошибка: пользователь с таким логином уже существует")

    st.markdown("### 📋 Список пользователей")
    users = get_all_users()
    if users:
        st.dataframe(
            data=[
                {
                    "ID": u["id"],
                    "Логин": u["username"],
                    "Роль": u["role"],
                    "Менеджер": u["manager_name"] or "-",
                }
                for u in users
            ],
            use_container_width=True,
        )
    else:
        st.info("ℹ️ Нет зарегистрированных пользователей")


def page_create_task():
    st.subheader("➕ Создать новую задачу")

    managers = get_managers_for_assignment()
    clients = get_clients_for_task()

    with st.form("create_task_form"):
        title = st.text_input("Название задачи*")
        description = st.text_area("Описание задачи*")

        col1, col2 = st.columns(2)
        with col1:
            client = st.selectbox("Клиент*", [""] + list(clients.keys()))
            deadline = st.date_input("Срок выполнения*")
        with col2:
            manager = st.selectbox(
                "Ответственный менеджер*", [""] + list(managers.keys())
            )

        submit = st.form_submit_button("💾 Создать задачу")

    if submit:
        if not all([title, description, client, manager, deadline]):
            st.error("🚨 Обязательные поля отмечены звездочкой*")
        elif create_task(
            title,
            description,
            clients[client],
            managers[manager],
            st.session_state.user_id,
            deadline,
        ):
            st.success("✅ Задача успешно создана!")
            rerun()
        else:
            st.error("⛔ Ошибка при создании задачи")


def page_tasks_dashboard():
    st.subheader("📊 Дашборд выполнения задач")

    data = get_manager_tasks_dashboard()

    st.markdown("### 📊 Статусы задач")
    if data["status_counts"]:
        st.bar_chart(data["status_counts"])
    else:
        st.info("ℹ️ Нет данных о задачах")

    st.markdown("### 👔 Распределение задач по менеджерам")
    if data["manager_counts"]:
        st.bar_chart(data["manager_counts"])
    else:
        st.info("ℹ️ Нет данных о задачах")

    st.markdown("### ⚠️ Просроченные задачи")
    st.metric("Количество просроченных задач", data["overdue_count"])

    st.markdown("### 📋 Все задачи")
    tasks = get_all_tasks()
    if tasks:
        st.dataframe(
            data=[
                {
                    "ID": t["id"],
                    "Задача": t["title"],
                    "Менеджер": t["manager_name"],
                    "Клиент": t["company_name"] or "-",
                    "Срок": t["deadline"],
                    "Статус": t["status"],
                }
                for t in tasks
            ],
            use_container_width=True,
            height=400,
        )
    else:
        st.info("ℹ️ Нет активных задач")


def page_add_manager():
    st.subheader("➕ Добавить нового менеджера")

    with st.form("add_manager_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("ФИО*")
            email = st.text_input("Email*")
        with col2:
            phone = st.text_input("Телефон")
            department = st.text_input("Отдел*")
        submit = st.form_submit_button("💾 Сохранить")

    if submit:
        if not all([name, email, department]):
            st.error("🚨 Обязательные поля отмечены звездочкой*")
        elif add_manager(name, email, phone, department):
            st.success("✅ Менеджер успешно добавлен!")
            rerun()
        else:
            st.error("⛔ Ошибка: менеджер с таким email уже существует")


def page_view_managers():
    st.subheader("📋 Список менеджеров")

    departments = ["Все"] + get_departments()
    selected = st.selectbox("🔍 Фильтр по отделу", departments)

    managers = get_all_managers()
    if selected != "Все":
        managers = [m for m in managers if m["department"] == selected]

    if managers:
        st.dataframe(
            data=[
                {
                    "ID": m["id"],
                    "ФИО": m["name"],
                    "Email": m["email"],
                    "Телефон": m["phone"] or "-",
                    "Отдел": m["department"] or "-",
                }
                for m in managers
            ],
            use_container_width=True,
            height=400,
        )
    else:
        st.info("ℹ️ Нет данных о менеджерах")


def page_view_clients():
    st.subheader("📑 Список клиентов")

    clients = get_all_clients()
    if clients:
        st.dataframe(
            data=[
                {
                    "ID": c["id"],
                    "Компания": c["company_name"],
                    "Контакт": c["contact_person"] or "-",
                    "Email": c["email"],
                    "Телефон": c["phone"] or "-",
                    "Менеджер": c["manager_name"] or "Не назначен",
                }
                for c in clients
            ],
            use_container_width=True,
            height=400,
        )
    else:
        st.info("ℹ️ Нет зарегистрированных клиентов")


# ------------------------------ Страницы: Manager -------------------------
def page_my_tasks():
    st.subheader("📋 Мои задачи")

    tasks = get_tasks_by_user(st.session_state.user_id)
    if not tasks:
        st.info("ℹ️ У вас нет активных задач")
        return

    for task in tasks:
        with st.expander(
            f"{task['title']} | Срок: {task['deadline']} | "
            f"Статус: {task['status']}"
        ):
            st.markdown(f"**Описание:** {task['description']}")
            st.markdown(f"**Клиент:** {task['company_name'] or '-'}")
            if task["created_at"]:
                st.markdown(
                    "**Создана:** "
                    f"{task['created_at'].strftime('%Y-%m-%d %H:%M')}"
                )

            new_status = st.selectbox(
                "Изменить статус",
                TASK_STATUSES,
                index=TASK_STATUSES.index(task["status"]),
                key=f"status_{task['id']}",
            )
            if st.button("Обновить статус", key=f"update_{task['id']}"):
                update_task_status(task["id"], new_status)
                st.success("✅ Статус обновлен!")
                rerun()


def page_client_tasks():
    st.subheader("🏭 Клиенты по задачам")

    tasks = get_tasks_by_user(st.session_state.user_id)
    if not tasks:
        st.info("ℹ️ У вас нет активных задач")
        return

    options = {f"Задача #{t['id']}: {t['title']}": t for t in tasks}
    selected_label = st.selectbox("Выберите задачу", list(options.keys()))
    task = options[selected_label]

    client = get_client_by_id(task["client_id"])
    if client is None:
        st.warning("⚠️ Информация о клиенте не найдена")
        return

    st.markdown("### Информация о клиенте")
    st.markdown(f"**Компания:** {client['company_name']}")
    st.markdown(f"**Контактное лицо:** {client['contact_person'] or '-'}")
    st.markdown(f"**Email:** {client['email']}")
    st.markdown(f"**Телефон:** {client['phone'] or '-'}")

    st.markdown("### 📝 Комментарии")
    if client["comments"]:
        st.text_area(
            "История комментариев",
            value=client["comments"],
            height=200,
            disabled=True,
            key=f"history_{client['id']}",
        )
    else:
        st.info("ℹ️ Комментариев пока нет")

    new_comment = st.text_area(
        "Добавить новый комментарий", key=f"comment_{client['id']}"
    )
    if st.button("💾 Сохранить комментарий", key=f"save_{client['id']}"):
        if new_comment.strip():
            add_comment_to_client(
                client["id"], new_comment, st.session_state.manager_name
            )
            st.success("✅ Комментарий добавлен!")
            rerun()
        else:
            st.warning("⚠️ Комментарий пуст")


# ------------------------------- Роутинг ----------------------------------
PAGE_HANDLERS = {
    "admin": {
        ADMIN_MENU[0]: page_users,
        ADMIN_MENU[1]: page_create_task,
        ADMIN_MENU[2]: page_tasks_dashboard,
        ADMIN_MENU[3]: page_add_manager,
        ADMIN_MENU[4]: page_view_managers,
        ADMIN_MENU[5]: page_view_clients,
    },
    "manager": {
        MANAGER_MENU[0]: page_my_tasks,
        MANAGER_MENU[1]: page_client_tasks,
    },
}


def login_page():
    st.title("🔐 Система управления менеджерами")

    with st.form("login_form"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submit = st.form_submit_button("Войти")

    if submit:
        user = authenticate(username, password)
        if user:
            st.session_state.authenticated = True
            st.session_state.user_id = user["id"]
            st.session_state.role = user["role"]
            st.session_state.manager_id = user["manager_id"]
            st.session_state.manager_name = user["manager_name"]
            rerun()
        else:
            st.error("Неверные учетные данные")


def main():
    st.set_page_config(page_title="Управление компанией", layout="wide")

    init_session_state()

    if not st.session_state.authenticated:
        login_page()
        return

    st.title(
        f"🏢 Управление менеджерами | "
        f"{st.session_state.manager_name or 'Администратор'}"
    )

    if st.sidebar.button("🚪 Выйти"):
        logout()
        rerun()

    role = st.session_state.role
    menu_items = ADMIN_MENU if role == "admin" else MANAGER_MENU
    menu = st.sidebar.selectbox("📋 Меню", menu_items)

    handler = PAGE_HANDLERS.get(role, {}).get(menu)
    if handler:
        handler()


# Инициализация схемы и первого администратора выполняется при импорте,
# чтобы страницы могли работать с готовой базой.
init_dbs()
create_first_admin()

if __name__ == "__main__":
    main()
