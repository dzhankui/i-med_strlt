import streamlit as st
import psycopg2
import os
from psycopg2 import IntegrityError


# Database connections
def get_db_connection(db_name):
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=db_name,
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD')
    )


# Initialize databases
def init_dbs():
    # Managers DB initialization
    with get_db_connection(os.getenv('MANAGERS_DB')) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS managers (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                department TEXT
            )
        ''')
        conn.commit()
    
# Clients DB initialization
with get_db_connection(os.getenv('CLIENTS_DB')) as conn:
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            company_name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            manager_id INTEGER REFERENCES managers(id)
        )
    ''')
conn.commit()


# ================== Manager Functions ==================
def add_manager(name, email, phone, department):
    with get_db_connection(os.getenv('MANAGERS_DB_NAME')) as conn:
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO managers (name, email, phone, department)
                VALUES (%s, %s, %s, %s)
            ''', (name, email, phone, department))
            conn.commit()
            return True
        except IntegrityError:
            return False


def get_all_managers():
    with get_db_connection(os.getenv('MANAGERS_DB_NAME')) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM managers ORDER BY id')
        return c.fetchall()


def update_manager(manager_id, name, email, phone, department):
    with get_db_connection(os.getenv('MANAGERS_DB_NAME')) as conn:
        c = conn.cursor()
        try:
            c.execute('''
                UPDATE managers SET
                name = %s,
                email = %s,
                phone = %s,
                department = %s
                WHERE id = %s
            ''', (name, email, phone, department, manager_id))
            conn.commit()
            return True
        except IntegrityError:
            return False


def delete_manager(manager_id):
    with get_db_connection(os.getenv('MANAGERS_DB_NAME')) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM managers WHERE id = %s', (manager_id,))
        conn.commit()


def get_departments():
    with get_db_connection(os.getenv('MANAGERS_DB_NAME')) as conn:
        c = conn.cursor()
        c.execute('SELECT DISTINCT department FROM managers ORDER BY department')
        return [row[0] for row in c.fetchall()]


def get_manager_by_id(manager_id):
    with get_db_connection(os.getenv('MANAGERS_DB_NAME')) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM managers WHERE id = %s', (manager_id,))
        return c.fetchone()


# ================== Client Functions ==================
def add_client(company, contact, email, phone, manager_id):
    with get_db_connection(os.getenv('CLIENTS_DB_NAME')) as conn:
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO clients
                (company_name, contact_person, email, phone, manager_id)
                VALUES (%s, %s, %s, %s, %s)
            ''', (company, contact, email, phone, manager_id))
            conn.commit()
            return True
        except IntegrityError:
            return False


def get_all_clients():
    with get_db_connection(os.getenv('CLIENTS_DB_NAME')) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT c.*, m.name
            FROM clients c
            LEFT JOIN managers m ON c.manager_id = m.id
            ORDER BY c.id
        ''')
        return c.fetchall()


def get_managers_for_dropdown():
    with get_db_connection(os.getenv('MANAGERS_DB_NAME')) as conn:
        c = conn.cursor()
        c.execute('SELECT id, name FROM managers ORDER BY name')
        return {row[1]: row[0] for row in c.fetchall()}


# ================== Streamlit Interface ==================
st.title('Управление компанией')

menu = st.sidebar.selectbox(
    'Меню',
    [
        'Менеджеры: Добавить',
        'Менеджеры: Просмотр',
        'Менеджеры: Редактировать',
        'Менеджеры: Удалить',
        'Клиенты: Добавить',
        'Клиенты: Просмотр'
    ]
)

# ================== Managers Section ==================
if menu == 'Менеджеры: Добавить':
    st.subheader('Добавить нового менеджера')
    with st.form(key='add_manager_form'):
        name = st.text_input('ФИО*')
        email = st.text_input('Email*')
        phone = st.text_input('Телефон')
        department = st.text_input('Отдел*')
        submit = st.form_submit_button('Сохранить')
    
    if submit:
        if not all([name, email, department]):
            st.error('Обязательные поля отмечены звездочкой*')
        else:
            success = add_manager(name, email, phone, department)
            if success:
                st.success('Менеджер успешно добавлен!')
            else:
                st.error('Ошибка: менеджер с таким email уже существует')

elif menu == 'Менеджеры: Просмотр':
    st.subheader('Список менеджеров')
    
    departments = ['Все'] + get_departments()
    selected_department = st.selectbox('Фильтр по отделу', departments)
    
    if selected_department == 'Все':
        managers = get_all_managers()
    else:
        with get_db_connection(os.getenv('MANAGERS_DB_NAME')) as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM managers WHERE department = %s ORDER BY id', (selected_department,))
            managers = c.fetchall()
    
    if managers:
        st.table([{
            'ID': m[0],
            'ФИО': m[1],
            'Email': m[2],
            'Телефон': m[3] or '-',
            'Отдел': m[4]
        } for m in managers])
    else:
        st.info('Нет данных о менеджерах')

elif menu == 'Менеджеры: Редактировать':
    st.subheader('Редактирование данных менеджера')
    managers = get_all_managers()
    
    if managers:
        manager_list = [f"{m[0]} - {m[1]}" for m in managers]
        selected_manager = st.selectbox('Выберите менеджера', manager_list)
        manager_id = int(selected_manager.split(' - ')[0])
        
        manager_data = get_manager_by_id(manager_id)
        
        with st.form(key='update_manager_form'):
            name = st.text_input('ФИО*', value=manager_data[1])
            email = st.text_input('Email*', value=manager_data[2])
            phone = st.text_input('Телефон', value=manager_data[3])
            department = st.text_input('Отдел*', value=manager_data[4])
            submit = st.form_submit_button('Обновить')
        
        if submit:
            if not all([name, email, department]):
                st.error('Обязательные поля отмечены звездочкой*')
            else:
                success = update_manager(manager_id, name, email, phone, department)
                if success:
                    st.success('Данные успешно обновлены!')
                else:
                    st.error('Ошибка: менеджер с таким email уже существует')
    else:
        st.info('Нет менеджеров для редактирования')

elif menu == 'Менеджеры: Удалить':
    st.subheader('Удаление менеджера')
    managers = get_all_managers()
    
    if managers:
        manager_list = [f"{m[0]} - {m[1]}" for m in managers]
        selected_manager = st.selectbox('Выберите менеджера для удаления', manager_list)
        manager_id = int(selected_manager.split(' - ')[0])
        
        if st.button('Удалить'):
            delete_manager(manager_id)
            st.success('Менеджер успешно удален!')
            st.experimental_rerun()
    else:
        st.info('Нет менеджеров для удаления')

# ================== Clients Section ==================
elif menu == 'Клиенты: Добавить':
    st.subheader('Добавить нового клиента')
    managers = get_managers_for_dropdown()
    
    with st.form(key='add_client_form'):
        company = st.text_input('Название компании*')
        contact = st.text_input('Контактное лицо')
        email = st.text_input('Email*')
        phone = st.text_input('Телефон')
        manager = st.selectbox('Ответственный менеджер', options=[''] + list(managers.keys()))
        submit = st.form_submit_button('Сохранить')
        
        if submit:
            if not all([company, email]):
                st.error('Обязательные поля отмечены звездочкой*')
            else:
                success = add_client(
                    company,
                    contact or None,
                    email,
                    phone or None,
                    managers.get(manager)
                )
                if success:
                    st.success('Клиент добавлен!')
                else:
                    st.error('Ошибка: клиент с таким email уже существует')

elif menu == 'Клиенты: Просмотр':
    st.subheader('Список клиентов')
    clients = get_all_clients()
    
    if clients:
        st.table([{
            'ID': c[0],
            'Компания': c[1],
            'Контакт': c[2] or '-',
            'Email': c[3],
            'Телефон': c[4] or '-',
            'Менеджер': c[5] or 'Не назначен'
        } for c in clients])
    else:
        st.info('Нет зарегистрированных клиентов')