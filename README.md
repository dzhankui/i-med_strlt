# Система управления менеджерами (Streamlit + PostgreSQL)

Веб-приложение для управления менеджерами, клиентами и задачами компании.
Построено на **Streamlit** и **PostgreSQL** (две базы: `managers` и `clients`),
разворачивается через **Docker Compose**.

## Архитектура

Код реконструирован в три явных слоя (файл `app/app.py`):

| Слой | Что содержит |
|---|---|
| **DB Layer** | `get_db_connection()` (context-manager с гарантированным закрытием), универсальный `run_query()` c `RealDictCursor`, DDL-скрипты `SCHEMA_MANAGERS` / `SCHEMA_CLIENTS`, `init_dbs()` |
| **Services** | Бизнес-функции по доменам: менеджеры (`add_manager`, `get_all_managers`, `get_departments`), клиенты (`add_client`, `get_all_clients`, `add_comment_to_client`), пользователи/аутентификация (`authenticate`, `create_user`, `create_first_admin`), задачи (`create_task`, `get_tasks_by_user`, `get_all_tasks`, `update_task_status`, `get_manager_tasks_dashboard`) |
| **UI** | Страницы Streamlit (`page_users`, `page_create_task`, `page_tasks_dashboard`, `page_add_manager`, `page_view_managers`, `page_view_clients`, `page_my_tasks`, `page_client_tasks`), ролевой роутинг `PAGE_HANDLERS`, `login_page()`, точка входа `main()` |

Данные о клиентах и менеджерах живут в разных базах, поэтому JOIN между ними
выполняется на уровне приложения (словари соответствий id → имя).

## Быстрый старт (Docker)

```bash
docker compose up --build
# Приложение: http://localhost:8501
```

Схема БД создаётся автоматически (`init.sql` + `init_dbs()` при старте приложения).

## Локальный запуск

Требования: Python 3.9+, доступный PostgreSQL с базами `managers` и `clients`.

```bash
cd app
pip install -r requirements.txt
export DB_HOST=localhost DB_USER=admin DB_PASSWORD=secret
streamlit run app.py
```

## Учётные данные по умолчанию

При первом запуске, если таблица `users` пуста, автоматически создаётся:

* логин: `admin`
* пароль: `admin123` (хранится как SHA-256 хеш)

## Роли

* **admin** — пользователи, создание задач, дашборд задач, менеджеры (добавление/просмотр), просмотр клиентов.
* **manager** — свои задачи (со сменой статуса), карточки клиентов по задачам с комментариями.

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DB_HOST` | `localhost` | адрес PostgreSQL |
| `DB_USER` | `admin` | пользователь |
| `DB_PASSWORD` | `secret` | пароль |
| `MANAGERS_DB` | `managers` | база менеджеров/пользователей/задач |
| `CLIENTS_DB` | `clients` | база клиентов |

## Примечания по безопасности

* Хеш SHA-256 без соли подходит только для демо; для продакшена рекомендуется
  `bcrypt`/`argon2`.
* Все SQL-запросы параметризуются (`%s`), что исключает SQL-инъекции.
