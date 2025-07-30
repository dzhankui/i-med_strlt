import streamlit as st
import psycopg2
import os
import hashlib
from datetime import datetime
from psycopg2 import OperationalError, IntegrityError


# Database configuration
def get_db_connection(db_name):
	return psycopg2.connect(
		host=os.getenv('DB_HOST'),
		database=db_name,
		user=os.getenv('DB_USER'),
		password=os.getenv('DB_PASSWORD')
	)


def create_first_admin():
    try:
        with get_db_connection("managers") as conn:
            with conn.cursor() as c:
                c.execute("SELECT COUNT(*) FROM users")
                if c.fetchone()[0] == 0:
                    c.execute(
                        "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                        ('admin', hashlib.sha256('admin123'.encode()).hexdigest(), 'admin')
                    )
                    conn.commit()
                    st.success("First admin created!")
    except Exception as e:
        st.error(f"Admin creation error: {e}")

create_first_admin()

# Initialize databases
def init_dbs():
	try:
		# Initialize managers database
		with get_db_connection("managers") as conn:
			with conn.cursor() as c:
				# Managers table
				c.execute('''
                    CREATE TABLE IF NOT EXISTS managers (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        phone TEXT,
                        department TEXT
                    )
                ''')
				
				# Users table
				c.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        role TEXT NOT NULL,
                        manager_id INTEGER REFERENCES managers(id) ON DELETE SET NULL
                    )
                ''')
				
				# Tasks table
				c.execute('''
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
                    )
                ''')
				conn.commit()
		
		# Initialize clients database
		with get_db_connection("clients") as conn:
			with conn.cursor() as c:
				# Clients table with comments
				c.execute('''
                    CREATE TABLE IF NOT EXISTS clients (
                        id SERIAL PRIMARY KEY,
                        company_name TEXT NOT NULL,
                        contact_person TEXT,
                        email TEXT UNIQUE NOT NULL,
                        phone TEXT,
                        manager_id INTEGER,
                        comments TEXT
                    )
                ''')
				conn.commit()
	
	except OperationalError as e:
		st.error(f"Ошибка подключения к БД: {str(e)}")
	except Exception as e:
		st.error(f"Ошибка инициализации: {str(e)}")


init_dbs()


# Password hashing
def hash_password(password):
	return hashlib.sha256(password.encode()).hexdigest()


# Authentication
def authenticate(username, password):
	try:
		with get_db_connection("managers") as conn:
			with conn.cursor() as c:
				c.execute('''
                    SELECT u.id, u.role, u.manager_id, m.name
                    FROM users u
                    LEFT JOIN managers m ON u.manager_id = m.id
                    WHERE username = %s AND password = %s
                ''', (username, hash_password(password)))
				user = c.fetchone()
				return user
	except Exception as e:
		st.error(f"Ошибка аутентификации: {str(e)}")
		return None


# ================== User Functions ==================
def create_user(username, password, role, manager_id=None):
	try:
		with get_db_connection("managers") as conn:
			with conn.cursor() as c:
				c.execute('''
                    INSERT INTO users (username, password, role, manager_id)
                    VALUES (%s, %s, %s, %s)
                ''', (username, hash_password(password), role, manager_id))
				conn.commit()
				return True
	except IntegrityError:
		return False


def get_all_users():
	with get_db_connection("managers") as conn:
		with conn.cursor() as c:
			c.execute('''
                SELECT u.id, u.username, u.role, m.name
                FROM users u
                LEFT JOIN managers m ON u.manager_id = m.id
                ORDER BY u.id
            ''')
			return c.fetchall()


def get_managers_for_assignment():
	with get_db_connection("managers") as conn:
		with conn.cursor() as c:
			c.execute('''
                SELECT u.id, m.name
                FROM users u
                JOIN managers m ON u.manager_id = m.id
                WHERE u.role = 'manager'
            ''')
			return {row[1]: row[0] for row in c.fetchall()}


# ================== Task Functions ==================
def create_task(title, description, client_id, assigned_to, created_by, deadline):
	try:
		with get_db_connection("managers") as conn:
			with conn.cursor() as c:
				c.execute('''
                    INSERT INTO tasks
                    (title, description, client_id, assigned_to, created_by, deadline)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (title, description, client_id, assigned_to, created_by, deadline))
				conn.commit()
				return True
	except Exception as e:
		st.error(f"Ошибка создания задачи: {str(e)}")
		return False


def get_tasks_by_user(user_id):
	with get_db_connection("managers") as conn:
		with conn.cursor() as c:
			c.execute('''
                SELECT t.id, t.title, t.description, c.company_name,
                       t.deadline, t.status, t.created_at
                FROM tasks t
                JOIN clients c ON t.client_id = c.id
                WHERE t.assigned_to = %s
                ORDER BY t.deadline
            ''', (user_id,))
			return c.fetchall()


def get_all_tasks():
	with get_db_connection("managers") as conn:
		with conn.cursor() as c:
			c.execute('''
                SELECT t.id, t.title, m.name AS manager_name,
                       c.company_name, t.deadline, t.status, t.created_at
                FROM tasks t
                JOIN users u ON t.assigned_to = u.id
                JOIN managers m ON u.manager_id = m.id
                JOIN clients c ON t.client_id = c.id
                ORDER BY t.deadline
            ''')
			return c.fetchall()


def update_task_status(task_id, status):
	with get_db_connection("managers") as conn:
		with conn.cursor() as c:
			c.execute('''
                UPDATE tasks SET status = %s WHERE id = %s
            ''', (status, task_id))
			conn.commit()


# ================== Client Functions ==================
def get_client_by_id(client_id):
	with get_db_connection("clients") as conn:
		with conn.cursor() as c:
			c.execute('SELECT * FROM clients WHERE id = %s', (client_id,))
			return c.fetchone()


def add_comment_to_client(client_id, comment, user_name):
	with get_db_connection("clients") as conn:
		with conn.cursor() as c:
			# Get existing comments
			c.execute('SELECT comments FROM clients WHERE id = %s', (client_id,))
			existing_comments = c.fetchone()[0] or ""
			
			# Add new comment with timestamp
			new_comment = f"{datetime.now().strftime('%Y-%m-%d %H:%M')} - {user_name}: {comment}\n"
			updated_comments = new_comment + existing_comments
			
			c.execute('''
                UPDATE clients SET comments = %s WHERE id = %s
            ''', (updated_comments, client_id))
			conn.commit()


def get_clients_for_task():
	with get_db_connection("clients") as conn:
		with conn.cursor() as c:
			c.execute('SELECT id, company_name FROM clients ORDER BY company_name')
			return {row[1]: row[0] for row in c.fetchall()}


# ================== Manager Functions ==================
def get_manager_tasks_dashboard():
	with get_db_connection("managers") as conn:
		with conn.cursor() as c:
			# Get task counts by status
			c.execute('''
                SELECT status, COUNT(*)
                FROM tasks
                GROUP BY status
            ''')
			status_counts = dict(c.fetchall())
			
			# Get tasks by manager
			c.execute('''
                SELECT m.name, COUNT(t.id)
                FROM tasks t
                JOIN users u ON t.assigned_to = u.id
                JOIN managers m ON u.manager_id = m.id
                GROUP BY m.name
            ''')
			manager_counts = dict(c.fetchall())
			
			# Get overdue tasks
			c.execute('''
                SELECT COUNT(*)
                FROM tasks
                WHERE deadline < CURRENT_DATE AND status != 'Завершена'
            ''')
			overdue_count = c.fetchone()[0]
			
			return {
				'status_counts': status_counts,
				'manager_counts': manager_counts,
				'overdue_count': overdue_count
			}


# ================== Streamlit Interface ==================
st.set_page_config(page_title="Управление компанией", layout="wide")

# Session state initialization
if 'authenticated' not in st.session_state:
	st.session_state.authenticated = False
	st.session_state.user_id = None
	st.session_state.role = None
	st.session_state.manager_id = None
	st.session_state.manager_name = None

# Login page
if not st.session_state.authenticated:
	st.title("🔐 Система управления менеджерами")
	
	with st.form("login_form"):
		username = st.text_input("Логин")
		password = st.text_input("Пароль", type="password")
		submit_button = st.form_submit_button("Войти")
		
		if submit_button:
			
			user = authenticate(username, password)
			if user:
				st.session_state.authenticated = True
				st.session_state.user_id = user[0]
				st.session_state.role = user[1]
				st.session_state.manager_id = user[2]
				st.session_state.manager_name = user[3]
				st.experimental_rerun()
			else:
				st.error("Неверные учетные данные")

# Main application
else:
	st.title(f"🏢 Управление менеджерами | {st.session_state.manager_name or 'Администратор'}")
	
	# Logout button
	if st.sidebar.button("🚪 Выйти"):
		st.session_state.authenticated = False
		st.experimental_rerun()
	
	# Admin menu
	if st.session_state.role == 'admin':
		menu = st.sidebar.selectbox(
			'📋 Меню',
			[
				'👥 Пользователи',
				'📋 Задачи: Создать',
				'📊 Задачи: Дашборд',
				'👔 Менеджеры: Добавить',
				'📋 Менеджеры: Просмотр',
				'🏭 Клиенты: Просмотр'
			]
		)
	# Manager menu
	else:
		menu = st.sidebar.selectbox(
			'📋 Меню',
			[
				'📋 Мои задачи',
				'🏭 Клиенты: Задачи'
			]
		)
	
	# ================== Admin Section ==================
	if menu == '👥 Пользователи' and st.session_state.role == 'admin':
		st.subheader("👥 Управление пользователями")
		
		# Create user form
		with st.expander("➕ Создать нового пользователя"):
			with st.form("create_user_form"):
				username = st.text_input("Логин*")
				password = st.text_input("Пароль*", type="password")
				role = st.selectbox("Роль*", ["admin", "manager"])
				
				# Get managers for assignment
				managers = get_managers_for_assignment()
				manager = st.selectbox("Менеджер", options=[''] + list(managers.keys()))
				
				submit = st.form_submit_button("💾 Создать")
				
				if submit:
					if not all([username, password, role]):
						st.error("🚨 Обязательные поля отмечены звездочкой*")
					else:
						success = create_user(
							username,
							password,
							role,
							managers.get(manager) if manager else None
						)
						if success:
							st.success("✅ Пользователь успешно создан!")
						else:
							st.error("⛔ Ошибка: пользователь с таким логином уже существует")
		
		# Users list
		st.subheader("📋 Список пользователей")
		users = get_all_users()
		if users:
			st.dataframe(
				data=[{
					'ID': u[0],
					'Логин': u[1],
					'Роль': u[2],
					'Менеджер': u[3] or '-'
				} for u in users],
				use_container_width=True
			)
		else:
			st.info("ℹ️ Нет зарегистрированных пользователей")
	
	elif menu == '📋 Задачи: Создать' and st.session_state.role == 'admin':
		st.subheader("➕ Создать новую задачу")
		
		# Get data for form
		managers = get_managers_for_assignment()
		clients = get_clients_for_task()
		
		with st.form("create_task_form"):
			title = st.text_input("Название задачи*")
			description = st.text_area("Описание задачи*")
			
			col1, col2 = st.columns(2)
			with col1:
				client = st.selectbox("Клиент*", options=[''] + list(clients.keys()))
				deadline = st.date_input("Срок выполнения*")
			with col2:
				manager = st.selectbox("Ответственный менеджер*", options=[''] + list(managers.keys()))
			
			submit = st.form_submit_button("💾 Создать задачу")
			
			if submit:
				if not all([title, description, client, manager, deadline]):
					st.error("🚨 Обязательные поля отмечены звездочкой*")
				else:
					success = create_task(
						title,
						description,
						clients[client],
						managers[manager],
						st.session_state.user_id,
						deadline
					)
					if success:
						st.success("✅ Задача успешно создана!")
					else:
						st.error("⛔ Ошибка при создании задачи")
	
	elif menu == '📊 Задачи: Дашборд' and st.session_state.role == 'admin':
		st.subheader("📊 Дашборд выполнения задач")
		
		dashboard_data = get_manager_tasks_dashboard()
		
		# Status summary
		st.markdown("### 📊 Статусы задач")
		if dashboard_data['status_counts']:
			st.bar_chart(dashboard_data['status_counts'])
		else:
			st.info("ℹ️ Нет данных о задачах")
		
		# Managers summary
		st.markdown("### 👔 Распределение задач по менеджерам")
		if dashboard_data['manager_counts']:
			st.bar_chart(dashboard_data['manager_counts'])
		else:
			st.info("ℹ️ Нет данных о задачах")
		
		# Overdue tasks
		st.markdown("### ⚠️ Просроченные задачи")
		st.metric("Количество просроченных задач", dashboard_data['overdue_count'])
		
		# All tasks list
		st.markdown("### 📋 Все задачи")
		tasks = get_all_tasks()
		if tasks:
			st.dataframe(
				data=[{
					'ID': t[0],
					'Задача': t[1],
					'Менеджер': t[2],
					'Клиент': t[3],
					'Срок': t[4],
					'Статус': t[5]
				} for t in tasks],
				use_container_width=True,
				height=400
			)
		else:
			st.info("ℹ️ Нет активных задач")
	
	# ================== Manager Section ==================
	elif menu == '📋 Мои задачи' and st.session_state.role == 'manager':
		st.subheader("📋 Мои задачи")
		
		tasks = get_tasks_by_user(st.session_state.user_id)
		if tasks:
			for task in tasks:
				with st.expander(f"{task[1]} | Срок: {task[4]} | Статус: {task[5]}"):
					st.markdown(f"**Описание:** {task[2]}")
					st.markdown(f"**Клиент:** {task[3]}")
					st.markdown(f"**Создана:** {task[6].strftime('%Y-%m-%d %H:%M')}")
					
					# Status update
					new_status = st.selectbox(
						"Изменить статус",
						["Новая", "В работе", "Завершена"],
						key=f"status_{task[0]}",
						index=["Новая", "В работе", "Завершена"].index(task[5])
					)
					
					if st.button("Обновить статус", key=f"update_{task[0]}"):
						update_task_status(task[0], new_status)
						st.success("✅ Статус обновлен!")
						st.experimental_rerun()
		else:
			st.info("ℹ️ У вас нет активных задач")
	
	elif menu == '🏭 Клиенты: Задачи' and st.session_state.role == 'manager':
		st.subheader("🏭 Клиенты по задачам")
		
		tasks = get_tasks_by_user(st.session_state.user_id)
		if tasks:
			task_ids = [t[0] for t in tasks]
			selected_task_id = st.selectbox(
				"Выберите задачу",
				task_ids,
				format_func=lambda x: f"Задача #{x}"
			)
			
			# Get selected task
			selected_task = next(t for t in tasks if t[0] == selected_task_id)
			
			# Get client details
			client_id = selected_task[3]  # company_name is at index 3, but we need client ID
			client = get_client_by_id(client_id)
			
			if client:
				st.markdown("### Информация о клиенте")
				st.markdown(f"**Компания:** {client[1]}")
				st.markdown(f"**Контактное лицо:** {client[2] or '-'}")
				st.markdown(f"**Email:** {client[3]}")
				st.markdown(f"**Телефон:** {client[4] or '-'}")
				
				# Comments section
				st.markdown("### 📝 Комментарии")
				if client[6]:
					st.text_area("История комментариев", value=client[6], height=200, disabled=True)
				else:
					st.info("ℹ️ Комментариев пока нет")
				
				# Add new comment
				new_comment = st.text_area("Добавить новый комментарий")
				if st.button("💾 Сохранить комментарий"):
					add_comment_to_client(
						client_id,
						new_comment,
						st.session_state.manager_name
					)
					st.success("✅ Комментарий добавлен!")
					st.experimental_rerun()
			else:
				st.warning("⚠️ Информация о клиенте не найдена")
		else:
			st.info("ℹ️ У вас нет активных задач")
	
	# ================== Common Admin/Manager Sections ==================
	# Manager management (admin only)
	if menu == '👔 Менеджеры: Добавить' and st.session_state.role == 'admin':
		st.subheader('➕ Добавить нового менеджера')
		with st.form(key='add_manager_form'):
			col1, col2 = st.columns(2)
			with col1:
				name = st.text_input('ФИО*')
				email = st.text_input('Email*')
			with col2:
				phone = st.text_input('Телефон')
				department = st.text_input('Отдел*')
			
			submit = st.form_submit_button('💾 Сохранить')
		
		if submit:
			if not all([name, email, department]):
				st.error('🚨 Обязательные поля отмечены звездочкой*')
			else:
				success = add_manager(name, email, phone, department)
				if success:
					st.success('✅ Менеджер успешно добавлен!')
				else:
					st.error('⛔ Ошибка: менеджер с таким email уже существует')
	
	elif menu == '📋 Менеджеры: Просмотр' and st.session_state.role == 'admin':
		st.subheader('📋 Список менеджеров')
		
		departments = ['Все'] + get_departments()
		selected_department = st.selectbox('🔍 Фильтр по отделу', departments)
		
		if selected_department == 'Все':
			managers = get_all_managers()
		else:
			with get_db_connection("managers") as conn:
				with conn.cursor() as c:
					c.execute('''
                        SELECT * FROM managers
                        WHERE department = %s
                        ORDER BY id
                    ''', (selected_department,))
					managers = c.fetchall()
		
		if managers:
			st.dataframe(
				data=[{
					'ID': m[0],
					'ФИО': m[1],
					'Email': m[2],
					'Телефон': m[3] or '-',
					'Отдел': m[4]
				} for m in managers],
				use_container_width=True,
				height=400
			)
		else:
			st.info('ℹ️ Нет данных о менеджерах')
	
	elif menu == '🏭 Клиенты: Просмотр' and st.session_state.role == 'admin':
		st.subheader('📑 Список клиентов')
		clients = get_all_clients()
		
		if clients:
			st.dataframe(
				data=[{
					'ID': c[0],
					'Компания': c[1],
					'Контакт': c[2] or '-',
					'Email': c[3],
					'Телефон': c[4] or '-',
					'Менеджер': c[5] or 'Не назначен'
				} for c in clients],
				use_container_width=True,
				height=400
			)
		else:
			st.info('ℹ️ Нет зарегистрированных клиентов')