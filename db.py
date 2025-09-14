import sqlite3
import os
from typing import Optional, Dict, Any, List


class Database:
    def __init__(self, db_name: str = 'bot_database.db'):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Инициализация таблиц базы данных"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()

            # Таблица для контента разделов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    photo_path TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица администраторов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица категорий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    photo_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица товаров
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    stars_price INTEGER DEFAULT 0,
                    category_id INTEGER NOT NULL,
                    activation_instruction TEXT,
                    photo_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories (id)
                )
            ''')

            # Таблица для хранения платежей через Stars
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS star_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    telegram_payment_charge_id TEXT UNIQUE,
                    provider_payment_charge_id TEXT,
                    payload TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            ''')

            # Проверяем и добавляем колонку section в таблицу categories если её нет
            cursor.execute("PRAGMA table_info(categories)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'section' not in columns:
                cursor.execute('ALTER TABLE categories ADD COLUMN section TEXT DEFAULT "operator"')
                print("Добавлена колонка section в таблицу categories")

            # Проверяем и добавляем колонку section в таблицу products если её нет
            cursor.execute("PRAGMA table_info(products)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'section' not in columns:
                cursor.execute('ALTER TABLE products ADD COLUMN section TEXT DEFAULT "operator"')
                print("Добавлена колонка section в таблицу products")

            # Проверяем и добавляем колонку stars_price в таблицу products если её нет
            cursor.execute("PRAGMA table_info(products)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'stars_price' not in columns:
                cursor.execute('ALTER TABLE products ADD COLUMN stars_price INTEGER DEFAULT 0')
                print("Добавлена колонка stars_price в таблицу products")

            # Проверяем и добавляем колонку activation_instruction в таблицу products если её нет
            cursor.execute("PRAGMA table_info(products)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'activation_instruction' not in columns:
                cursor.execute('ALTER TABLE products ADD COLUMN activation_instruction TEXT')
                print("Добавлена колонка activation_instruction в таблицу products")

            # Добавляем начальные данные для разделов
            default_sections = [
                ('about_shop',
                 '🏪 <b>О нашем магазине</b>\n\nМы - лучший магазин с многолетной историей и тысячами довольных клиентов!',
                 None),
                ('promotions',
                 '🎁 <b>Акции и скидки</b>\n\nСледите за нашими акции и специальными предложениями!',
                 None)
            ]

            for section_name, content, photo_path in default_sections:
                cursor.execute(
                    'INSERT OR IGNORE INTO sections (name, content, photo_path) VALUES (?, ?, ?)',
                    (section_name, content, photo_path)
                )

            # Добавляем администраторов
            admins = [
                (785219206, 'azikk', 'Администратор'),
                (1927067668, None, 'Второй администратор')
            ]

            for user_id, username, full_name in admins:
                cursor.execute(
                    'INSERT OR IGNORE INTO admins (user_id, username, full_name) VALUES (?, ?, ?)',
                    (user_id, username, full_name)
                )

            conn.commit()

    def get_section_content(self, section_name: str) -> Optional[str]:
        """Получить контент раздела по имени"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT content FROM sections WHERE name = ?',
                (section_name,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def get_section_photo(self, section_name: str) -> Optional[str]:
        """Получить путь к фотографии раздела"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT photo_path FROM sections WHERE name = ?',
                (section_name,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def update_section_content(self, section_name: str, content: str) -> bool:
        """Обновить контент раздела"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE sections SET content = ? WHERE name = ?',
                (content, section_name)
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_section_photo(self, section_name: str, photo_path: str) -> bool:
        """Обновить фотографию раздела"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE sections SET photo_path = ? WHERE name = ?',
                (photo_path, section_name)
            )
            conn.commit()
            return cursor.rowcount > 0

    def add_category(self, name: str, description: str = None, photo_path: str = None,
                     section: str = 'operator') -> bool:
        """Добавить новую категорию с указанием раздела"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO categories (name, description, photo_path, section) VALUES (?, ?, ?, ?)',
                    (name, description, photo_path, section)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False

    def get_category_by_id(self, category_id: int) -> Optional[Dict[str, Any]]:
        """Получить категорию по ID"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, name, description, photo_path, section FROM categories WHERE id = ?',
                (category_id,)
            )
            result = cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "name": result[1],
                    "description": result[2],
                    "photo_path": result[3],
                    "section": result[4]
                }
            return None

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """Получить все категории"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, name, description, photo_path, section FROM categories ORDER BY name'
            )
            return [{
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "photo_path": row[3],
                "section": row[4]
            } for row in cursor.fetchall()]

    def get_categories_by_section(self, section: str) -> List[Dict[str, Any]]:
        """Получить все категории по разделу"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, name, description, photo_path, section FROM categories WHERE section = ? ORDER BY name',
                (section,)
            )
            return [{
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "photo_path": row[3],
                "section": row[4]
            } for row in cursor.fetchall()]

    def delete_category(self, category_id: int) -> bool:
        """Удалить категорию"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM categories WHERE id = ?',
                (category_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def add_product(self, name: str, description: str, price: float, stars_price: int, category_id: int,
                    activation_instruction: str = None, photo_path: str = None, section: str = 'operator') -> bool:
        """Добавить новый товар"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO products 
                    (name, description, price, stars_price, category_id, activation_instruction, photo_path, section) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (name, description, price, stars_price, category_id, activation_instruction, photo_path, section)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error:
            return False

    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Получить товар по ID"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT id, name, description, price, stars_price, category_id, activation_instruction, photo_path, section 
                FROM products WHERE id = ?''',
                (product_id,)
            )
            result = cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "name": result[1],
                    "description": result[2],
                    "price": result[3],
                    "stars_price": result[4],
                    "category_id": result[5],
                    "activation_instruction": result[6],
                    "photo_path": result[7],
                    "section": result[8]
                }
            return None

    def get_products_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        """Получить все товары категории"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT id, name, description, price, stars_price, category_id, activation_instruction, photo_path, section 
                FROM products WHERE category_id = ? ORDER BY name''',
                (category_id,)
            )
            return [{
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price": row[3],
                "stars_price": row[4],
                "category_id": row[5],
                "activation_instruction": row[6],
                "photo_path": row[7],
                "section": row[8]
            } for row in cursor.fetchall()]

    def get_products_by_category_and_section(self, category_id: int, section: str) -> List[Dict[str, Any]]:
        """Получить все товары категории по разделу"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT id, name, description, price, stars_price, category_id, activation_instruction, photo_path, section 
                FROM products WHERE category_id = ? AND section = ? ORDER BY name''',
                (category_id, section)
            )
            return [{
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price": row[3],
                "stars_price": row[4],
                "category_id": row[5],
                "activation_instruction": row[6],
                "photo_path": row[7],
                "section": row[8]
            } for row in cursor.fetchall()]

    def delete_product(self, product_id: int) -> bool:
        """Удалить товар"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM products WHERE id = ?',
                (product_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM admins WHERE user_id = ?',
                (user_id,)
            )
            return cursor.fetchone() is not None

    def create_star_payment(self, user_id: int, product_id: int, amount: int, payload: str) -> Optional[int]:
        """Создать запись о платеже Stars"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO star_payments 
                    (user_id, product_id, amount, payload) 
                    VALUES (?, ?, ?, ?)''',
                    (user_id, product_id, amount, payload)
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error:
            return None

    def update_star_payment_status(self, payment_id: int, status: str,
                                   telegram_payment_charge_id: str = None,
                                   provider_payment_charge_id: str = None) -> bool:
        """Обновить статус платежа Stars"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()

            if telegram_payment_charge_id and provider_payment_charge_id:
                cursor.execute(
                    '''UPDATE star_payments 
                    SET status = ?, telegram_payment_charge_id = ?, provider_payment_charge_id = ?
                    WHERE id = ?''',
                    (status, telegram_payment_charge_id, provider_payment_charge_id, payment_id)
                )
            else:
                cursor.execute(
                    'UPDATE star_payments SET status = ? WHERE id = ?',
                    (status, payment_id)
                )

            conn.commit()
            return cursor.rowcount > 0

    def get_star_payment_by_id(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """Получить информацию о платеже Stars по ID"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT id, user_id, product_id, amount, telegram_payment_charge_id, 
                provider_payment_charge_id, payload, created_at, status 
                FROM star_payments WHERE id = ?''',
                (payment_id,)
            )
            result = cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "user_id": result[1],
                    "product_id": result[2],
                    "amount": result[3],
                    "telegram_payment_charge_id": result[4],
                    "provider_payment_charge_id": result[5],
                    "payload": result[6],
                    "created_at": result[7],
                    "status": result[8]
                }
            return None

    def get_star_payment_by_payload(self, payload: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о платеже Stars по payload"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT id, user_id, product_id, amount, telegram_payment_charge_id, 
                provider_payment_charge_id, payload, created_at, status 
                FROM star_payments WHERE payload = ?''',
                (payload,)
            )
            result = cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "user_id": result[1],
                    "product_id": result[2],
                    "amount": result[3],
                    "telegram_payment_charge_id": result[4],
                    "provider_payment_charge_id": result[5],
                    "payload": result[6],
                    "created_at": result[7],
                    "status": result[8]
                }
            return None


# Создаем глобальный экземпляр базы данных
db = Database()