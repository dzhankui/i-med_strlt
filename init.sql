CREATE DATABASE clients;

\c clients;

CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_person TEXT,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    manager_id INTEGER REFERENCES managers(id)
);