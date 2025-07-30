-- Создаем основную базу данных для менеджеров
CREATE DATABASE managers;

\c managers;

CREATE TABLE managers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    department TEXT
);

-- Создаем базу данных для клиентов
CREATE DATABASE clients;

\c clients;

CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_person TEXT,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    manager_id INTEGER
);
-- В базе managers
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

-- В базе clients
ALTER TABLE clients ADD COLUMN IF NOT EXISTS comments TEXT;
