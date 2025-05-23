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