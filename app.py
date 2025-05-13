import streamlit as st
import sqlite3
import re

# CSS для изменения фона
st.markdown(
	"""
	<style>
	.stApp {
		background-color: rgb(129, 216, 208);
	}

	h1, h2, h3, h4, h5, h6 {
		color: rgb(0, 0, 0);
	}
	
	div.stButton > button {0, 0, 0}
	
	</style>
	""",
	unsafe_allow_html=True
)


# Создание подключения к базе данных
conn = sqlite3.connect('managers.db')
c = conn.cursor()


# Создание таблицы менеджеров
def create_table():
	c.execute('''CREATE TABLE IF NOT EXISTS managers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  phone TEXT,
                  department TEXT)''')
	conn.commit()


create_table()


# Функции для работы с базой данных
def add_manager(name, email, phone, department):
	c.execute('INSERT INTO managers (name, email, phone, department) VALUES (?, ?, ?, ?)',
	          (name, email, phone, department))
	conn.commit()


def get_all_managers():
	c.execute('SELECT * FROM managers')
	return c.fetchall()


def update_manager(manager_id, name, email, phone, department):
	c.execute('''UPDATE managers SET
                 name = ?,
                 email = ?,
                 phone = ?,
                 department = ?
                 WHERE id = ?''',
	          (name, email, phone, department, manager_id))
	conn.commit()


def delete_manager(manager_id):
	c.execute('DELETE FROM managers WHERE id = ?', (manager_id,))
	conn.commit()


def get_departments():
	c.execute('SELECT DISTINCT department FROM managers')
	return [row[0] for row in c.fetchall()]


# Интерфейс Streamlit
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
		try:
			add_manager(name, email, phone, department)
			st.success('Менеджер успешно добавлен!')
		except sqlite3.IntegrityError:
			st.error('Ошибка: менеджер с таким email уже существует')

elif menu == 'Просмотр менеджеров':
	st.subheader('Список менеджеров')
	
	# Фильтрация по отделу
	departments = ['Все'] + get_departments()
	selected_department = st.selectbox('Фильтр по отделу', departments)
	
	if selected_department == 'Все':
		managers = get_all_managers()
	else:
		c.execute('SELECT * FROM managers WHERE department = ?', (selected_department,))
		managers = c.fetchall()
	
	if managers:
		st.table(managers)
	else:
		st.info('Нет данных о менеджерах')

elif menu == 'Обновить данные':
	st.subheader('Обновить данные менеджера')
	managers = get_all_managers()
	
	if managers:
		manager_list = [f"{m[0]} - {m[1]}" for m in managers]
		selected_manager = st.selectbox('Выберите менеджера', manager_list)
		manager_id = int(selected_manager.split(' - ')[0])
		
		# Получение текущих данных
		c.execute('SELECT * FROM managers WHERE id = ?', (manager_id,))
		manager_data = c.fetchone()
		
		with st.form(key='update_form'):
			name = st.text_input('ФИО', value=manager_data[1])
			email = st.text_input('Email', value=manager_data[2])
			phone = st.text_input('Телефон', value=manager_data[3])
			department = st.text_input('Отдел', value=manager_data[4])
			submit_button = st.form_submit_button(label='Обновить')
		
		if submit_button:
			try:
				update_manager(manager_id, name, email, phone, department)
				st.success('Данные успешно обновлены!')
			except sqlite3.IntegrityError:
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
	else:
		st.info('Нет менеджеров для удаления')

# Закрытие соединения при завершении
conn.close()