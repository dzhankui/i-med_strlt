import streamlit as st
import psycopg2
import os
from psycopg2 import IntegrityError


# Database connection
def get_db_connection():
	return psycopg2.connect(
		host=os.getenv('DB_HOST'),
		database=os.getenv('DB_NAME'),
		user=os.getenv('DB_USER'),
		password=os.getenv('DB_PASSWORD')
	)


# Create tables
def init_db():
	conn = get_db_connection()
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
	conn.close()


init_db()


# Database functions
def add_manager(name, email, phone, department):
	conn = get_db_connection()
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
	finally:
		conn.close()


def get_all_managers():
	conn = get_db_connection()
	c = conn.cursor()
	c.execute('SELECT * FROM managers ORDER BY id')
	managers = c.fetchall()
	conn.close()
	return managers


def update_manager(manager_id, name, email, phone, department):
	conn = get_db_connection()
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
	finally:
		conn.close()


def delete_manager(manager_id):
	conn = get_db_connection()
	c = conn.cursor()
	c.execute('DELETE FROM managers WHERE id = %s', (manager_id,))
	conn.commit()
	conn.close()


def get_departments():
	conn = get_db_connection()
	c = conn.cursor()
	c.execute('SELECT DISTINCT department FROM managers ORDER BY department')
	departments = [row[0] for row in c.fetchall()]
	conn.close()
	return departments


def get_manager_by_id(manager_id):
	conn = get_db_connection()
	c = conn.cursor()
	c.execute('SELECT * FROM managers WHERE id = %s', (manager_id,))
	manager = c.fetchone()
	conn.close()
	return manager


# Streamlit Interface
st.title('Управление отделом менеджеров')

menu = st.sidebar.selectbox(
	'Меню',
	['Добавить менеджера', 'Просмотр менеджеров', 'Обновить данные', 'Удалить менеджера']
)

if menu == 'Добавить менеджера':
	st.subheader('Добавить нового менеджера')
	with st.form(key='add_form'):
		name = st.text_input('ФИО')
		email = st.text_input('Email')
		phone = st.text_input('Телефон')
		department = st.text_input('Отдел')
		submit_button = st.form_submit_button(label='Добавить')
	
	if submit_button:
		if not all([name, email, department]):
			st.error('Поля ФИО, Email и Отдел обязательны для заполнения')
		else:
			success = add_manager(name, email, phone, department)
			if success:
				st.success('Менеджер успешно добавлен!')
			else:
				st.error('Ошибка: менеджер с таким email уже существует')

elif menu == 'Просмотр менеджеров':
	st.subheader('Список менеджеров')
	
	departments = ['Все'] + get_departments()
	selected_department = st.selectbox('Фильтр по отделу', departments)
	
	if selected_department == 'Все':
		managers = get_all_managers()
	else:
		conn = get_db_connection()
		c = conn.cursor()
		c.execute('SELECT * FROM managers WHERE department = %s ORDER BY id', (selected_department,))
		managers = c.fetchall()
		conn.close()
	
	if managers:
		headers = ['ID', 'ФИО', 'Email', 'Телефон', 'Отдел']
		rows = [[m[0], m[1], m[2], m[3] if m[3] else '-', m[4]] for m in managers]
		st.table(dict(zip(headers, zip(*rows))))
	else:
		st.info('Нет данных о менеджерах')

elif menu == 'Обновить данные':
	st.subheader('Обновить данные менеджера')
	managers = get_all_managers()
	
	if managers:
		manager_list = [f"{m[0]} - {m[1]}" for m in managers]
		selected_manager = st.selectbox('Выберите менеджера', manager_list)
		manager_id = int(selected_manager.split(' - ')[0])
		
		manager_data = get_manager_by_id(manager_id)
		
		with st.form(key='update_form'):
			name = st.text_input('ФИО', value=manager_data[1])
			email = st.text_input('Email', value=manager_data[2])
			phone = st.text_input('Телефон', value=manager_data[3])
			department = st.text_input('Отдел', value=manager_data[4])
			submit_button = st.form_submit_button(label='Обновить')
		
		if submit_button:
			if not all([name, email, department]):
				st.error('Поля ФИО, Email и Отдел обязательны для заполнения')
			else:
				success = update_manager(manager_id, name, email, phone, department)
				if success:
					st.success('Данные успешно обновлены!')
				else:
					st.error('Ошибка: менеджер с таким email уже существует')
	else:
		st.info('Нет менеджеров для обновления')

elif menu == 'Удалить менеджера':
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