from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import datetime as dt
import os
import logging
from typing import Optional
import time
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from sqlalchemy import text, and_

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Получаем DATABASE_URL из переменных окружения
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    # Локальная разработка
    database_url = 'postgresql://postgres:1234@localhost/calckal'
    
# Исправляем URL для psycopg3 (Render использует postgres:// вместо postgresql://)
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Добавляем настройки для продакшена
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_timeout': 20,
    'pool_recycle': -1,
    'pool_pre_ping': True
}

# Добавляем настройки для предотвращения кэширования
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

db = SQLAlchemy(app)

# Функции для управления сессиями
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Для доступа к этой странице необходимо войти в систему.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get current user from session"""
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            return user
    return None

# Функции для системы уровней
def get_or_create_user_level(user_id: int) -> 'UserLevel':
    """Получить или создать запись об уровне пользователя"""
    user_level = UserLevel.query.filter_by(user_id=user_id).first()
    if not user_level:
        user_level = UserLevel(user_id=user_id)
        db.session.add(user_level)
        db.session.commit()
        logging.info(f"Created new level record for user {user_id}")
    return user_level

def award_experience(user_id: int, points: int, activity_type: str, description: str = '') -> dict:
    """Наградить пользователя опытом"""
    try:
        user_level = get_or_create_user_level(user_id)
        old_level = user_level.level
        
        new_level = user_level.add_experience(points, activity_type)
        db.session.commit()
        
        result = {
            'success': True,
            'experience_gained': points,
            'total_experience': user_level.experience,
            'old_level': old_level,
            'new_level': new_level,
            'level_up': new_level > old_level,
            'progress_percentage': user_level.progress_percentage,
            'title': user_level.title,
            'activity': description or activity_type
        }
        
        logging.info(f"User {user_id} gained {points} XP for {activity_type}. Level: {old_level} -> {new_level}")
        return result
        
    except Exception as e:
        logging.error(f"Error awarding experience to user {user_id}: {str(e)}")
        return {'success': False, 'error': str(e)}

def check_achievements(user_level: 'UserLevel'):
    """Проверить и выдать достижения"""
    new_achievements = []
    
    # Достижения по уровням
    level_achievements = {
        5: ('лвл_5', '🌱 Первые шаги'),
        10: ('лвл_10', '🥈 Опытный пользователь'),
        20: ('лвл_20', '🥇 Продвинутый трекер'),
        30: ('лвл_30', '⭐ Эксперт питания'),
        50: ('лвл_50', '🏆 Мастер Питания')
    }
    
    for level_req, (ach_id, ach_name) in level_achievements.items():
        if user_level.level >= level_req:
            if user_level.add_achievement(ach_id, ach_name):
                new_achievements.append(ach_name)
    
    # Достижения по активности
    activity_achievements = {
        10: ('актив_10', '📅 10 дней активности'),
        30: ('актив_30', '📅 30 дней активности'),
        100: ('актив_100', '📅 100 дней активности')
    }
    
    for days_req, (ach_id, ach_name) in activity_achievements.items():
        if user_level.days_active >= days_req:
            if user_level.add_achievement(ach_id, ach_name):
                new_achievements.append(ach_name)
    
    # Достижения по записям еды
    food_achievements = {
        50: ('еда_50', '🍽️ 50 записей о еде'),
        100: ('еда_100', '🍽️ 100 записей о еде'),
        500: ('еда_500', '🍽️ 500 записей о еде')
    }
    
    for entries_req, (ach_id, ach_name) in food_achievements.items():
        if user_level.total_food_entries >= entries_req:
            if user_level.add_achievement(ach_id, ach_name):
                new_achievements.append(ach_name)
    
    return new_achievements

# Модели базы данных
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    profile = db.relationship('UserProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    food_entries = db.relationship('FoodEntry', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, username: str, password: str, email: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'
class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    calories_per_100g = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, default=0)
    carbs = db.Column(db.Float, default=0)
    fat = db.Column(db.Float, default=0)
    category = db.Column(db.String(50), default='Прочее')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, name: str, calories_per_100g: float, protein: float = 0, carbs: float = 0, fat: float = 0, category: str = 'Прочее', **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.calories_per_100g = calories_per_100g
        self.protein = protein
        self.carbs = carbs
        self.fat = fat
        self.category = category
    
    def __repr__(self):
        return f'<Product {self.name}>'

class FoodEntry(db.Model):
    __tablename__ = 'food_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    weight = db.Column(db.Float, nullable=False)  # вес в граммах
    date = db.Column(db.Date, nullable=False, default=dt.date.today)
    meal_type = db.Column(db.String(20), nullable=False)  # завтрак, обед, ужин, перекус
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', backref=db.backref('entries', lazy=True))
    
    def __init__(self, user_id: int, product_id: int, weight: float, meal_type: str, date: Optional[dt.date] = None, **kwargs):
        super().__init__(**kwargs)
        self.user_id = user_id
        self.product_id = product_id
        self.weight = weight
        self.meal_type = meal_type
        if date is not None:
            self.date = date
    
    @property
    def total_calories(self):
        return (self.product.calories_per_100g * self.weight) / 100
    
    @property
    def total_protein(self):
        return (self.product.protein * self.weight) / 100
    
    @property
    def total_carbs(self):
        return (self.product.carbs * self.weight) / 100
    
    @property
    def total_fat(self):
        return (self.product.fat * self.weight) / 100

class UserProfile(db.Model):
    __tablename__ = 'user_profile'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))  # male/female
    weight = db.Column(db.Float)  # текущий вес
    height = db.Column(db.Float)  # рост в см
    activity_level = db.Column(db.String(20))  # sedentary, light, moderate, active, very_active
    goal = db.Column(db.String(20))  # lose, maintain, gain
    target_calories = db.Column(db.Integer)  # целевые калории в день
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, user_id: int, name: str, age: Optional[int] = None, gender: Optional[str] = None, 
                 weight: Optional[float] = None, height: Optional[float] = None, 
                 activity_level: Optional[str] = None, goal: Optional[str] = None, 
                 target_calories: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.user_id = user_id
        self.name = name
        self.age = age
        self.gender = gender
        self.weight = weight
        self.height = height
        self.activity_level = activity_level
        self.goal = goal
        self.target_calories = target_calories

class UserLevel(db.Model):
    __tablename__ = 'user_levels'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    level = db.Column(db.Integer, default=1)
    experience = db.Column(db.Integer, default=0)
    total_food_entries = db.Column(db.Integer, default=0)
    total_products_added = db.Column(db.Integer, default=0)
    days_active = db.Column(db.Integer, default=0)
    last_activity_date = db.Column(db.Date)
    achievements = db.Column(db.Text)  # JSON строка с полученными достижениями
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с пользователем
    user = db.relationship('User', backref=db.backref('level_info', uselist=False))
    
    def __init__(self, user_id: int, **kwargs):
        super().__init__(**kwargs)
        self.user_id = user_id
        self.achievements = '[]'  # Пустой JSON массив
    
    @property
    def experience_to_next_level(self):
        """Опыт, необходимый для следующего уровня"""
        return self.level * 100
    
    @property
    def progress_percentage(self):
        """Процент прогресса до следующего уровня"""
        current_level_exp = (self.level - 1) * 100
        next_level_exp = self.level * 100
        level_progress = self.experience - current_level_exp
        level_requirement = next_level_exp - current_level_exp
        return min(100, (level_progress / level_requirement) * 100) if level_requirement > 0 else 100
    
    @property
    def title(self):
        """Титул пользователя в зависимости от уровня"""
        if self.level >= 50:
            return "🏆 Мастер Питания"
        elif self.level >= 30:
            return "⭐ Эксперт"
        elif self.level >= 20:
            return "🥇 Продвинутый"
        elif self.level >= 10:
            return "🥈 Опытный"
        elif self.level >= 5:
            return "🥉 Новичок+"
        else:
            return "🌱 Новичок"
    
    def add_experience(self, points: int, activity_type: str):
        """Добавить опыт и проверить повышение уровня"""
        self.experience += points
        
        # Проверяем повышение уровня
        while self.experience >= self.level * 100:
            self.level += 1
        
        # Обновляем статистику активности
        today = dt.date.today()
        if activity_type == 'food_entry':
            self.total_food_entries += 1
        elif activity_type == 'product_added':
            self.total_products_added += 1
        
        # Обновляем дни активности
        if self.last_activity_date != today:
            self.days_active += 1
            self.last_activity_date = today
        
        self.updated_at = datetime.utcnow()
        
        return self.level  # Возвращаем текущий уровень
    
    def get_achievements(self):
        """Получить список достижений"""
        import json
        try:
            return json.loads(self.achievements or '[]')
        except:
            return []
    
    def add_achievement(self, achievement_id: str, achievement_name: str):
        """Добавить достижение"""
        import json
        achievements = self.get_achievements()
        
        if achievement_id not in [a['id'] for a in achievements]:
            achievements.append({
                'id': achievement_id,
                'name': achievement_name,
                'earned_at': datetime.utcnow().isoformat()
            })
            self.achievements = json.dumps(achievements)
            return True
        return False

# Добавляем мидлвар для обеспечения свежих данных
@app.before_request
def refresh_database_session():
    """Рефреш базы данных сессия перед каждым запросом для обеспечения свежих данных"""
    try:
        db.session.expire_all()
    except Exception as e:
        logging.warning(f"Ошибка обновления базы данных сессия: {str(e)}")

@app.after_request
def add_cache_headers(response):
    """Добавить cache-control заголовки для предотвращения кэширования динамических данных"""
    if request.endpoint in ['index', 'products', 'add_food', 'profile', 'statistics']:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# Инициализация базы данных при импорте модуля (для gunicorn)
def init_database():
    """Initialize database tables and default data"""
    try:
        with app.app_context():
            logging.info("Starting database initialization...")
            
            # Создаем все таблицы
            db.create_all()
            logging.info("Database tables created successfully")
            
            # Проверяем, что таблицы действительно созданы
            from sqlalchemy import text
            result = db.session.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            ))
            tables = [row[0] for row in result]
            logging.info(f"Created tables: {tables}")
            
            # Добавляем все продукты автоматически
            auto_load_all_products()
            
            # Инициализируем систему уровней для существующих пользователей
            init_user_levels_for_existing_users()
            
    except Exception as e:
        logging.error(f"Error initializing database: {str(e)}")
        # Не поднимаем исключение, чтобы приложение продолжило работать

def auto_load_all_products():
    """Автоматически загружает все доступные продукты при инициализации"""
    try:
        current_count = Product.query.count()
        logging.info(f"Current product count: {current_count}")
        
        if current_count == 0:
            logging.info("Loading initial products...")
            
            # Базовые продукты
            default_products = [
                    # Хлебобулочные изделия
                    Product(name="Хлеб белый", calories_per_100g=265, protein=8.1, carbs=48.8, fat=3.2, category="Хлебобулочные"),
                    Product(name="Хлеб черный", calories_per_100g=214, protein=6.6, carbs=40.7, fat=1.3, category="Хлебобулочные"),
                    Product(name="Хлеб ржаной", calories_per_100g=181, protein=6.6, carbs=34.2, fat=1.2, category="Хлебобулочные"),
                    Product(name="Батон нарезной", calories_per_100g=264, protein=7.5, carbs=50.9, fat=2.9, category="Хлебобулочные"),
                    Product(name="Булочка с маком", calories_per_100g=336, protein=7.8, carbs=55.5, fat=9.9, category="Хлебобулочные"),
                    Product(name="Круассан", calories_per_100g=406, protein=8.2, carbs=45.8, fat=20.9, category="Хлебобулочные"),
                    Product(name="Багет", calories_per_100g=262, protein=8.1, carbs=51.4, fat=3.3, category="Хлебобулочные"),
                    Product(name="Лаваш тонкий", calories_per_100g=236, protein=7.9, carbs=47.6, fat=1.2, category="Хлебобулочные"),
                    Product(name="Тортилья", calories_per_100g=218, protein=5.7, carbs=43.2, fat=2.9, category="Хлебобулочные"),
                    Product(name="Сухари панировочные", calories_per_100g=347, protein=11.2, carbs=72.1, fat=1.8, category="Хлебобулочные"),

                    # Молочные продукты
                    Product(name="Молоко 3.2%", calories_per_100g=60, protein=2.9, carbs=4.7, fat=3.2, category="Молочные"),
                    Product(name="Молоко 2.5%", calories_per_100g=54, protein=2.8, carbs=4.7, fat=2.5, category="Молочные"),
                    Product(name="Молоко 1.5%", calories_per_100g=47, protein=3.0, carbs=4.9, fat=1.5, category="Молочные"),
                    Product(name="Молоко обезжиренное", calories_per_100g=35, protein=3.4, carbs=5.0, fat=0.1, category="Молочные"),
                    Product(name="Сливки 10%", calories_per_100g=118, protein=3.0, carbs=4.0, fat=10.0, category="Молочные"),
                    Product(name="Сливки 20%", calories_per_100g=206, protein=2.8, carbs=3.7, fat=20.0, category="Молочные"),
                    Product(name="Сметана 15%", calories_per_100g=158, protein=2.6, carbs=3.0, fat=15.0, category="Молочные"),
                    Product(name="Сметана 20%", calories_per_100g=206, protein=2.8, carbs=3.2, fat=20.0, category="Молочные"),
                    Product(name="Творог 0%", calories_per_100g=88, protein=16.7, carbs=1.3, fat=0.6, category="Молочные"),
                    Product(name="Творог 5%", calories_per_100g=121, protein=17.2, carbs=1.8, fat=5.0, category="Молочные"),
                    Product(name="Творог 9%", calories_per_100g=159, protein=16.7, carbs=2.0, fat=9.0, category="Молочные"),
                    Product(name="Йогурт натуральный", calories_per_100g=66, protein=5.0, carbs=3.5, fat=3.2, category="Молочные"),
                    Product(name="Кефир 1%", calories_per_100g=40, protein=2.8, carbs=4.0, fat=1.0, category="Молочные"),
                    Product(name="Кефир 2.5%", calories_per_100g=53, protein=2.8, carbs=4.0, fat=2.5, category="Молочные"),
                    Product(name="Ряженка 4%", calories_per_100g=67, protein=2.9, carbs=4.2, fat=4.0, category="Молочные"),
                    Product(name="Простокваша", calories_per_100g=58, protein=2.9, carbs=4.1, fat=3.2, category="Молочные"),

                    # Сыры
                    Product(name="Сыр российский", calories_per_100g=364, protein=23.2, carbs=0.3, fat=29.5, category="Сыры"),
                    Product(name="Сыр голландский", calories_per_100g=352, protein=26.8, carbs=0.0, fat=26.8, category="Сыры"),
                    Product(name="Сыр швейцарский", calories_per_100g=396, protein=24.9, carbs=0.0, fat=31.8, category="Сыры"),
                    Product(name="Сыр моцарелла", calories_per_100g=280, protein=22.2, carbs=2.2, fat=22.4, category="Сыры"),
                    Product(name="Сыр пармезан", calories_per_100g=431, protein=38.0, carbs=1.0, fat=29.0, category="Сыры"),
                    Product(name="Сыр фета", calories_per_100g=264, protein=14.2, carbs=4.1, fat=21.3, category="Сыры"),
                    Product(name="Сыр чеддер", calories_per_100g=402, protein=25.0, carbs=1.3, fat=33.1, category="Сыры"),
                    Product(name="Сыр камамбер", calories_per_100g=299, protein=19.8, carbs=0.5, fat=24.3, category="Сыры"),
                    Product(name="Сыр творожный", calories_per_100g=342, protein=22.6, carbs=4.1, fat=26.2, category="Сыры"),
                    Product(name="Сыр плавленый", calories_per_100g=257, protein=16.8, carbs=23.8, fat=11.2, category="Сыры"),

                    # Мясо и птица
                    Product(name="Говядина постная", calories_per_100g=158, protein=22.2, carbs=0.0, fat=7.1, category="Мясо и птица"),
                    Product(name="Свинина постная", calories_per_100g=142, protein=20.9, carbs=0.0, fat=6.1, category="Мясо и птица"),
                    Product(name="Баранина", calories_per_100g=203, protein=16.3, carbs=0.0, fat=15.3, category="Мясо и птица"),
                    Product(name="Телятина", calories_per_100g=97, protein=19.7, carbs=0.0, fat=1.2, category="Мясо и птица"),
                    Product(name="Курица грудка", calories_per_100g=165, protein=31.0, carbs=0.0, fat=3.6, category="Мясо и птица"),
                    Product(name="Курица бедро", calories_per_100g=185, protein=16.8, carbs=0.0, fat=12.8, category="Мясо и птица"),
                    Product(name="Курица крылья", calories_per_100g=186, protein=19.2, carbs=0.0, fat=12.2, category="Мясо и птица"),
                    Product(name="Индейка грудка", calories_per_100g=84, protein=19.2, carbs=0.0, fat=0.7, category="Мясо и птица"),
                    Product(name="Утка", calories_per_100g=308, protein=16.0, carbs=0.0, fat=27.8, category="Мясо и птица"),
                    Product(name="Гусь", calories_per_100g=319, protein=16.1, carbs=0.0, fat=28.2, category="Мясо и птица"),
                    Product(name="Кролик", calories_per_100g=156, protein=20.7, carbs=0.0, fat=7.8, category="Мясо и птица"),

                    # Колбасные изделия
                    Product(name="Колбаса докторская", calories_per_100g=257, protein=13.7, carbs=1.5, fat=22.8, category="Колбасные изделия"),
                    Product(name="Колбаса копченая", calories_per_100g=511, protein=16.2, carbs=0.0, fat=47.8, category="Колбасные изделия"),
                    Product(name="Сосиски молочные", calories_per_100g=266, protein=11.0, carbs=1.6, fat=23.9, category="Колбасные изделия"),
                    Product(name="Сардельки", calories_per_100g=332, protein=10.1, carbs=1.8, fat=31.6, category="Колбасные изделия"),
                    Product(name="Ветчина", calories_per_100g=279, protein=22.6, carbs=0.0, fat=20.9, category="Колбасные изделия"),
                    Product(name="Бекон", calories_per_100g=500, protein=23.0, carbs=0.0, fat=45.0, category="Колбасные изделия"),
                    Product(name="Салями", calories_per_100g=568, protein=13.0, carbs=1.0, fat=57.0, category="Колбасные изделия")]
                
            for product in default_products:
                db.session.add(product)
                
                db.session.commit()
                logging.info(f"Added {len(default_products)} initial products")
            
            # Добавляем расширенные продукты если их мало
            if current_count < 50:
                logging.info("Adding extended product set...")
                load_extended_products()
            
            # Добавляем мега-набор продуктов
            if current_count < 150:
                logging.info("Adding mega product set...")
                load_mega_products_auto()
            
            final_count = Product.query.count()
            logging.info(f"Product loading completed. Total products: {final_count}")
            
    except Exception as e:
        logging.error(f"Error in auto_load_all_products: {str(e)}")

def init_user_levels_for_existing_users():
    """Инициализируем систему уровней для существующих пользователей"""
    try:
        users_without_levels = db.session.execute(
            text("""
                SELECT u.id FROM users u 
                LEFT JOIN user_levels ul ON u.id = ul.user_id 
                WHERE ul.user_id IS NULL
            """)
        ).fetchall()
        
        for user_row in users_without_levels:
            user_id = user_row[0]
            
            # Подсчитываем статистику пользователя
            food_entries_count = db.session.execute(
                text("SELECT COUNT(*) FROM food_entries WHERE user_id = :user_id"),
                {'user_id': user_id}
            ).scalar() or 0
            
            # Подсчитываем уникальные дни активности
            active_days = db.session.execute(
                text("SELECT COUNT(DISTINCT date) FROM food_entries WHERE user_id = :user_id"),
                {'user_id': user_id}
            ).scalar() or 0
            
            # Получаем последнюю дату активности
            last_activity = db.session.execute(
                text("SELECT MAX(date) FROM food_entries WHERE user_id = :user_id"),
                {'user_id': user_id}
            ).scalar()
            
            # Рассчитываем опыт на основе активности
            experience = (food_entries_count * 10) + (active_days * 25)
            level = max(1, experience // 100)
            
            # Создаем запись об уровне
            user_level = UserLevel(
                user_id=user_id,
                level=level,
                experience=experience,
                total_food_entries=food_entries_count,
                days_active=active_days,
                last_activity_date=last_activity
            )
            
            db.session.add(user_level)
            logging.info(f"Initialized level {level} (XP: {experience}) for user {user_id}")
        
        db.session.commit()
        logging.info(f"Initialized levels for {len(users_without_levels)} existing users")
        
    except Exception as e:
        logging.error(f"Error initializing user levels: {str(e)}")
        db.session.rollback()

def load_extended_products():
    """Добавляет расширенный набор продуктов"""
    extended_products = [
        # Рыба и морепродукты
        Product(name="Судак", calories_per_100g=84, protein=19.0, carbs=0.0, fat=0.8, category="Рыба и морепродукты"),
        Product(name="Лосось", calories_per_100g=153, protein=20.0, carbs=0.0, fat=8.1, category="Рыба и морепродукты"),
        Product(name="Тунец", calories_per_100g=96, protein=23.0, carbs=0.0, fat=1.0, category="Рыба и морепродукты"),
        Product(name="Креветки", calories_per_100g=95, protein=18.9, carbs=0.8, fat=2.2, category="Рыба и морепродукты"),
        # Овощи
        Product(name="Капуста цветная", calories_per_100g=30, protein=2.5, carbs=4.2, fat=0.3, category="Овощи"),
        Product(name="Перец болгарский", calories_per_100g=27, protein=1.3, carbs=5.3, fat=0.1, category="Овощи"),
        Product(name="Чеснок", calories_per_100g=143, protein=6.5, carbs=29.9, fat=0.5, category="Овощи"),
        Product(name="Свекла", calories_per_100g=40, protein=1.5, carbs=8.8, fat=0.1, category="Овощи"),
        # Фрукты
        Product(name="Мандарин", calories_per_100g=38, protein=0.8, carbs=7.5, fat=0.2, category="Фрукты"),
        Product(name="Лимон", calories_per_100g=16, protein=0.9, carbs=3.0, fat=0.1, category="Фрукты"),
        Product(name="Виноград", calories_per_100g=65, protein=0.6, carbs=15.4, fat=0.2, category="Фрукты"),
        Product(name="Киви", calories_per_100g=47, protein=1.0, carbs=10.3, fat=0.5, category="Фрукты")
    ]
    
    added_count = 0
    for product in extended_products:
        existing = Product.query.filter_by(name=product.name).first()
        if not existing:
            db.session.add(product)
            added_count += 1
    
    db.session.commit()
    logging.info(f"Added {added_count} extended products")

def load_mega_products_auto():
    """Добавляет мега-набор продуктов"""
    mega_products = [
        # Орехи и семечки
        Product(name="Фундук", calories_per_100g=704, protein=16.1, carbs=9.9, fat=66.9, category="Орехи и семечки"),
        Product(name="Арахис", calories_per_100g=548, protein=26.3, carbs=9.9, fat=45.2, category="Орехи и семечки"),
        Product(name="Кешью", calories_per_100g=553, protein=25.7, carbs=13.2, fat=42.2, category="Орехи и семечки"),
        # Крупы
        Product(name="Рис бурый", calories_per_100g=337, protein=6.3, carbs=65.1, fat=4.4, category="Крупы"),
        Product(name="Перловка", calories_per_100g=315, protein=9.3, carbs=73.7, fat=1.1, category="Крупы"),
        Product(name="Булгур", calories_per_100g=342, protein=12.3, carbs=57.6, fat=1.3, category="Крупы"),
        # Бобовые
        Product(name="Фасоль белая", calories_per_100g=102, protein=7.0, carbs=16.9, fat=0.5, category="Бобовые"),
        Product(name="Нут", calories_per_100g=364, protein=19.3, carbs=61.0, fat=6.0, category="Бобовые"),
        # Напитки
        Product(name="Чай черный", calories_per_100g=1, protein=0.0, carbs=0.3, fat=0.0, category="Напитки"),
        Product(name="Сок апельсиновый", calories_per_100g=36, protein=0.7, carbs=8.1, fat=0.2, category="Напитки"),
        # Сладости
        Product(name="Шоколад молочный", calories_per_100g=534, protein=7.6, carbs=60.2, fat=29.7, category="Сладости"),
        Product(name="Мед", calories_per_100g=329, protein=0.8, carbs=80.3, fat=0.0, category="Сладости")
    ]
    
    added_count = 0
    for product in mega_products:
        existing = Product.query.filter_by(name=product.name).first()
        if not existing:
            db.session.add(product)
            added_count += 1
    
    db.session.commit()
    logging.info(f"Added {added_count} mega products")

# Добавляем функцию для ленивой инициализации
def ensure_tables_exist():
    """Ensure database tables exist, create them if they don't"""
    try:
        # Проверяем существование таблицы food_entries
        from sqlalchemy import text
        result = db.session.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'food_entries')"
        ))
        table_exists = result.scalar()
        
        if not table_exists:
            logging.warning("Tables don't exist, creating them now...")
            init_database()
            return True
        return False
    except Exception as e:
        logging.error(f"Error checking table existence: {str(e)}")
        return False

def migrate_food_entries_table():
    """Migrate food_entries table to add missing user_id column"""
    try:
        from sqlalchemy import text
        logging.info("Starting food_entries table migration...")
        
        # Check if food_entries table exists
        table_check = db.session.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'food_entries')"
        ))
        table_exists = table_check.scalar()
        
        if not table_exists:
            logging.info("food_entries table doesn't exist, creating it...")
            db.create_all()
            logging.info("food_entries table created successfully")
            return True
        
        # Check if user_id column exists
        column_check = db.session.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='food_entries' AND column_name='user_id'"
        ))
        user_id_exists = column_check.fetchone() is not None
        
        if not user_id_exists:
            logging.info("user_id column missing in food_entries, adding it...")
            
            # First, check if there are existing records
            record_count = db.session.execute(text("SELECT COUNT(*) FROM food_entries")).scalar() or 0
            logging.info(f"Found {record_count} existing records in food_entries")
            
            # Add the user_id column
            db.session.execute(text("ALTER TABLE food_entries ADD COLUMN user_id INTEGER"))
            
            if record_count > 0:
                # If there are existing records, we need to handle them
                # First, get the first user ID from users table
                first_user = db.session.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
                if first_user:
                    first_user_id = first_user[0]
                    logging.info(f"Assigning existing food entries to user_id: {first_user_id}")
                    
                    # Update existing records to point to the first user
                    db.session.execute(text(
                        "UPDATE food_entries SET user_id = :user_id WHERE user_id IS NULL"
                    ), {'user_id': first_user_id})
                else:
                    # No users exist, create a default user
                    logging.info("No users found, creating default user for food entries...")
                    default_password_hash = 'pbkdf2:sha256:600000$default$c8c1a3d4e5f6789abc123def456789abc123def456789abc123def456789abc'
                    db.session.execute(text(
                        "INSERT INTO users (username, password_hash, created_at) VALUES ('admin', :password_hash, NOW())"
                    ), {'password_hash': default_password_hash})
                    
                    # Get the new user ID
                    new_user = db.session.execute(text("SELECT id FROM users WHERE username = 'admin'")).fetchone()
                    if new_user:
                        new_user_id = new_user[0]
                        db.session.execute(text(
                            "UPDATE food_entries SET user_id = :user_id WHERE user_id IS NULL"
                        ), {'user_id': new_user_id})
            
            # Make the column NOT NULL after updating existing records
            db.session.execute(text("ALTER TABLE food_entries ALTER COLUMN user_id SET NOT NULL"))
            
            # Add foreign key constraint
            try:
                db.session.execute(text(
                    "ALTER TABLE food_entries ADD CONSTRAINT fk_food_entries_user_id FOREIGN KEY (user_id) REFERENCES users(id)"
                ))
            except Exception as fk_error:
                logging.warning(f"Could not add foreign key constraint to food_entries: {fk_error}")
            
            db.session.commit()
            logging.info("user_id column added to food_entries successfully")
            return True
        else:
            logging.info("food_entries table already has user_id column")
            return False
            
    except Exception as e:
        logging.error(f"Error during food_entries migration: {str(e)}")
        db.session.rollback()
        raise

def migrate_user_profile_table():
    """Migrate user_profile table to add missing columns"""
    try:
        from sqlalchemy import text
        logging.info("Starting user_profile table migration...")
        
        # Check if user_profile table exists
        table_check = db.session.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_profile')"
        ))
        table_exists = table_check.scalar()
        
        if not table_exists:
            logging.info("user_profile table doesn't exist, creating it...")
            db.create_all()
            logging.info("user_profile table created successfully")
            return True
        
        # Check if user_id column exists
        column_check = db.session.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='user_profile' AND column_name='user_id'"
        ))
        user_id_exists = column_check.fetchone() is not None
        
        if not user_id_exists:
            logging.info("user_id column missing, adding it...")
            
            # First, check if there are existing records
            record_count = db.session.execute(text("SELECT COUNT(*) FROM user_profile")).scalar() or 0
            logging.info(f"Found {record_count} existing records in user_profile")
            
            # Add the user_id column
            db.session.execute(text("ALTER TABLE user_profile ADD COLUMN user_id INTEGER"))
            
            if record_count > 0:
                # If there are existing records, we need to handle them
                # First, get the first user ID from users table
                first_user = db.session.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
                if first_user:
                    first_user_id = first_user[0]
                    logging.info(f"Assigning existing profiles to user_id: {first_user_id}")
                    
                    # Update existing records to point to the first user
                    db.session.execute(text(
                        "UPDATE user_profile SET user_id = :user_id WHERE user_id IS NULL"
                    ), {'user_id': first_user_id})
                else:
                    # No users exist, create a default user
                    logging.info("No users found, creating default user...")
                    db.session.execute(text(
                        "INSERT INTO users (username, password_hash, created_at) VALUES ('admin', 'pbkdf2:sha256:600000$default$hash', NOW())"
                    ))
                    
                    # Get the new user ID
                    new_user = db.session.execute(text("SELECT id FROM users WHERE username = 'admin'")).fetchone()
                    if new_user:
                        new_user_id = new_user[0]
                        db.session.execute(text(
                            "UPDATE user_profile SET user_id = :user_id WHERE user_id IS NULL"
                        ), {'user_id': new_user_id})
            
            # Make the column NOT NULL after updating existing records
            db.session.execute(text("ALTER TABLE user_profile ALTER COLUMN user_id SET NOT NULL"))
            
            # Add foreign key constraint
            try:
                db.session.execute(text(
                    "ALTER TABLE user_profile ADD CONSTRAINT fk_user_profile_user_id FOREIGN KEY (user_id) REFERENCES users(id)"
                ))
            except Exception as fk_error:
                logging.warning(f"Could not add foreign key constraint: {fk_error}")
            
            # Add unique constraint
            try:
                db.session.execute(text(
                    "ALTER TABLE user_profile ADD CONSTRAINT uq_user_profile_user_id UNIQUE (user_id)"
                ))
            except Exception as uq_error:
                logging.warning(f"Could not add unique constraint: {uq_error}")
            
            db.session.commit()
            logging.info("user_id column added successfully")
            return True
        else:
            logging.info("user_profile table already has user_id column")
            return False
            
    except Exception as e:
        logging.error(f"Error during user_profile migration: {str(e)}")
        db.session.rollback()
        raise

def check_and_migrate_schema():
    """Check database schema and perform necessary migrations"""
    try:
        logging.info("Checking database schema...")
        
        # Ensure basic tables exist
        ensure_tables_exist()
        
        # Migrate food_entries table if needed
        migrate_food_entries_table()
        
        # Migrate user_profile table if needed
        migrate_user_profile_table()
        
        logging.info("Schema check completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"Schema migration failed: {str(e)}")
        return False

# Инициализируем базу данных при загрузке модуля
try:
    logging.info("Attempting initial database setup...")
    with app.app_context():
        init_database()
        # Проверяем и мигрируем схему
        check_and_migrate_schema()
except Exception as e:
    logging.error(f"Failed to initialize database on startup: {str(e)}")

# Маршруты аутентификации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        email = request.form.get('email', '').strip() or None
        
        # Проверка данных
        if not username or len(username) < 3:
            flash('Логин должен быть не менее 3 символов', 'error')
            return render_template('register.html')
        
        if not password or len(password) < 4:
            flash('Пароль должен быть не менее 4 символов', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return render_template('register.html')
        
        # Проверка уникальности логина
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Пользователь с таким логином уже существует', 'error')
            return render_template('register.html')
        
        try:
            # Создаем нового пользователя
            user = User(username=username, password=password, email=email)
            db.session.add(user)
            db.session.commit()
            
            # Автоматически входим в систему
            session['user_id'] = user.id
            session['username'] = user.username
            
            flash(f'Добро пожаловать, {username}! Учётная запись успешно создана.', 'success')
            return redirect(url_for('profile'))  # Направляем на создание профиля
            
        except Exception as e:
            logging.error(f"Registration error: {str(e)}")
            flash('Ошибка при создании учётной записи. Попробуйте снова.', 'error')
            db.session.rollback()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            
            next_page = request.args.get('next')
            flash(f'Привет, {username}!', 'success')
            
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'Пользователь')
    session.clear()
    flash(f'До свидания, {username}!', 'info')
    return redirect(url_for('login'))

# Основные маршруты
@app.route('/')
@login_required
def index():
    try:
        # Проверяем существование таблиц перед обращением к ним
        try:
            check_and_migrate_schema()
        except Exception as migration_error:
            logging.warning(f"Migration check failed, continuing anyway: {migration_error}")
        
        # Принудительное обновление сессии для получения свежих данных
        db.session.expire_all()
        
        current_user = get_current_user()
        if not current_user:
            flash('Ошибка аутентификации. Пожалуйста, войдите в систему снова.', 'error')
            return redirect(url_for('login'))
        
        today = dt.date.today()
        
        # Получаем записи за сегодня для текущего пользователя
        today_entries = FoodEntry.query.filter_by(user_id=current_user.id, date=today).all()
        
        # Подсчитываем общие калории за день
        total_calories = sum(entry.total_calories for entry in today_entries)
        total_protein = sum(entry.total_protein for entry in today_entries)
        total_carbs = sum(entry.total_carbs for entry in today_entries)
        total_fat = sum(entry.total_fat for entry in today_entries)
        
        # Группируем по типам приема пищи
        meals = {
            'завтрак': [],
            'обед': [],
            'ужин': [],
            'перекус': []
        }
        
        for entry in today_entries:
            if entry.meal_type in meals:
                meals[entry.meal_type].append(entry)
        
        # Получаем профиль текущего пользователя
        profile = UserProfile.query.filter_by(user_id=current_user.id).first()
        target_calories = profile.target_calories if profile and profile.target_calories else 2000
        
        # Получаем информацию о уровне пользователя
        user_level = get_or_create_user_level(current_user.id)
        
        return render_template('index.html', 
                             meals=meals,
                             total_calories=total_calories,
                             total_protein=total_protein,
                             total_carbs=total_carbs,
                             total_fat=total_fat,
                             target_calories=target_calories,
                             today=today,
                             current_user=current_user,
                             user_level=user_level)
    except Exception as e:
        logging.error(f"Database error in index route: {str(e)}")
        flash('Ошибка подключения к базе данных. Проверьте настройки подключения.', 'error')
        return render_template('index.html', 
                             meals={'завтрак': [], 'обед': [], 'ужин': [], 'перекус': []},
                             total_calories=0,
                             total_protein=0,
                             total_carbs=0,
                             total_fat=0,
                             target_calories=2000,
                             today=dt.date.today(),
                             current_user=get_current_user(),
                             user_level=None)

@app.route('/products')
@login_required
def products():
    # Принудительное обновление сессии для получения свежих данных
    db.session.expire_all()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    # Логируем запрос к странице продуктов
    total_products = Product.query.count()
    logging.info(f"Запрос к /products - всего продуктов в БД: {total_products}, страница: {page}, поиск: '{search}', категория: '{category}'")
    
    query = Product.query
    
    # Фильтрация по категории
    if category:
        query = query.filter(Product.category.ilike(f'%{category}%'))  # type: ignore
        filtered_count = query.count()
        logging.info(f"После фильтрации по категории '{category}': {filtered_count} продуктов")
    
    # Фильтрация по поиску
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))  # type: ignore
        filtered_count = query.count()
        logging.info(f"После фильтрации по поиску '{search}': {filtered_count} продуктов")
    
    products = query.order_by(Product.category, Product.name).paginate(page=page, per_page=20, error_out=False)
    logging.info(f"Пагинация: страница {page}, показано {len(products.items)} из {products.total} продуктов")
    
    return render_template('products.html', products=products, search=search, category=category, today=dt.date.today())

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        try:
            name = request.form['name']
            calories = float(request.form['calories'])
            protein = float(request.form.get('protein', 0))
            carbs = float(request.form.get('carbs', 0))
            fat = float(request.form.get('fat', 0))
            category = request.form.get('category', 'Прочее')
            
            # Проверяем, нет ли уже такого продукта
            existing_product = Product.query.filter_by(name=name).first()
            if existing_product:
                flash(f'Продукт "{name}" уже существует в базе!', 'warning')
                return redirect(url_for('products', search=name))
            
            product = Product(
                name=name,
                calories_per_100g=calories,
                protein=protein,
                carbs=carbs,
                fat=fat,
                category=category
            )
            
            db.session.add(product)
            db.session.commit()
            
            # Награждаем опытом за добавление нового продукта
            current_user = get_current_user()
            xp_result = None  # Инициализируем переменную
            if current_user:
                xp_result = award_experience(
                    user_id=current_user.id,
                    points=25,  # 25 XP за добавление нового продукта
                    activity_type='product_added',
                    description=f'Добавление нового продукта: {name}'
                )
            
            # Принудительно очищаем кэш для всех сессий
            db.session.expire_all()
            
            logging.info(f"Новый продукт добавлен: {name} ({category}) - {calories} ккал/100г")
            
            success_message = f'Продукт "{name}" успешно добавлен! Теперь он доступен всем пользователям!'
            
            # Добавляем информацию об опыте
            if current_user and xp_result and xp_result.get('success'):
                success_message += f' | +{xp_result["experience_gained"]} XP'
                if xp_result.get('level_up'):
                    success_message += f' | 🎉 Новый уровень: {xp_result["new_level"]}! {xp_result["title"]}'
            
            flash(success_message, 'success')
            
            # Перенаправляем на страницу продуктов с фильтром по категории
            return redirect(url_for('products', category=category, search=name))
            
        except ValueError as e:
            flash('Ошибка в числовых значениях. Проверьте данные.', 'danger')
        except Exception as e:
            logging.error(f"Ошибка при добавлении продукта: {str(e)}")
            flash(f'Ошибка при добавлении продукта: {str(e)}', 'danger')
    
    return render_template('add_product.html')

@app.route('/add_food', methods=['GET', 'POST'])
@login_required
def add_food():
    if request.method == 'POST':
        meal_type = request.form['meal_type']
        entry_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        current_user = get_current_user()
        if not current_user:
            flash('Ошибка аутентификации. Пожалуйста, войдите в систему снова.', 'error')
            return redirect(url_for('login'))
        
        added_count = 0
        
        # Обрабатываем множественные продукты
        product_ids = request.form.getlist('product_id[]')
        weights = request.form.getlist('weight[]')
        
        for i, product_id in enumerate(product_ids):
            if product_id and i < len(weights) and weights[i]:
                try:
                    food_entry = FoodEntry(
                        user_id=current_user.id,
                        product_id=int(product_id),
                        weight=float(weights[i]),
                        meal_type=meal_type,
                        date=entry_date
                    )
                    db.session.add(food_entry)
                    added_count += 1
                except (ValueError, IndexError):
                    continue
        
        if added_count > 0:
            db.session.commit()
            
            # Награждаем опытом за добавление еды
            xp_result = award_experience(
                user_id=current_user.id,
                points=10 * added_count,  # 10 XP за каждый продукт
                activity_type='food_entry',
                description=f'Добавление {added_count} продуктов в дневник'
            )
            
            # Принудительно очищаем кэш для обновления данных
            db.session.expire_all()
            
            success_message = f'Добавлено {added_count} продуктов в дневник!'
            
            # Добавляем информацию об опыте
            if xp_result.get('success'):
                success_message += f' | +{xp_result["experience_gained"]} XP'
                if xp_result.get('level_up'):
                    success_message += f' | 🎉 Новый уровень: {xp_result["new_level"]}! {xp_result["title"]}'
            
            flash(success_message, 'success')
        else:
            flash('Не удалось добавить продукты. Проверьте данные.', 'danger')
        
        return redirect(url_for('index'))
    
    # Принудительное обновление сессии для получения свежих продуктов
    db.session.expire_all()
    products = Product.query.order_by(Product.category, Product.name).all()
    selected_product_id = request.args.get('product', type=int)
    return render_template('add_food.html', products=products, today=dt.date.today(), selected_product_id=selected_product_id)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    try:
        # Проверяем существование таблиц перед обращением к ним
        try:
            check_and_migrate_schema()
        except Exception as migration_error:
            logging.warning(f"Migration check failed, continuing anyway: {migration_error}")
        
        # Принудительное обновление сессии для получения свежих данных
        db.session.expire_all()
        
        current_user = get_current_user()
        if not current_user:
            flash('Ошибка аутентификации. Пожалуйста, войдите в систему снова.', 'error')
            return redirect(url_for('login'))
        
        user_profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    
        if request.method == 'POST':
            name = request.form['name']
            age = int(request.form['age'])
            gender = request.form['gender']
            weight = float(request.form['weight'])
            height = float(request.form['height'])
            activity_level = request.form['activity_level']
            goal = request.form['goal']
            
            # Расчет целевых калорий по формуле Миффлина-Сан Жеора
            if gender == 'male':
                bmr = 10 * weight + 6.25 * height - 5 * age + 5
            else:
                bmr = 10 * weight + 6.25 * height - 5 * age - 161
            
            # Коэффициенты активности
            activity_multipliers = {
                'sedentary': 1.2,
                'light': 1.375,
                'moderate': 1.55,
                'active': 1.725,
                'very_active': 1.9
            }
            
            tdee = bmr * activity_multipliers.get(activity_level, 1.2)
            
            # Корректировка по цели
            if goal == 'lose':
                target_calories = int(tdee - 500)  # дефицит 500 ккал
            elif goal == 'gain':
                target_calories = int(tdee + 500)  # профицит 500 ккал
            else:
                target_calories = int(tdee)
            
            if user_profile:
                user_profile.name = name
                user_profile.age = age
                user_profile.gender = gender
                user_profile.weight = weight
                user_profile.height = height
                user_profile.activity_level = activity_level
                user_profile.goal = goal
                user_profile.target_calories = target_calories
            else:
                user_profile = UserProfile(
                    user_id=current_user.id,
                    name=name,
                    age=age,
                    gender=gender,
                    weight=weight,
                    height=height,
                    activity_level=activity_level,
                    goal=goal,
                    target_calories=target_calories
                )
                db.session.add(user_profile)
            
            db.session.commit()
            flash('Профиль обновлен!', 'success')
            return redirect(url_for('profile'))
        
        return render_template('profile.html', profile=user_profile, current_user=current_user)
        
    except Exception as e:
        logging.error(f"Database error in profile route: {str(e)}")
        flash(f'Ошибка загрузки профиля: {str(e)}', 'error')
        
        # Попробуем выполнить миграцию
        try:
            logging.info("Attempting to fix database schema...")
            with app.app_context():
                check_and_migrate_schema()
            flash('Попытка исправления схемы базы данных выполнена. Попробуйте обновить страницу.', 'info')
        except Exception as migration_error:
            logging.error(f"Migration fix failed: {str(migration_error)}")
            flash(f'Не удалось исправить схему базы данных: {str(migration_error)}', 'error')
        
        # Возвращаем страницу с пустым профилем
        return render_template('profile.html', profile=None, current_user=get_current_user())

@app.route('/statistics')
@login_required
def statistics():
    # Принудительное обновление сессии для получения свежих данных
    db.session.expire_all()
    
    current_user = get_current_user()
    if not current_user:
        flash('Ошибка аутентификации. Пожалуйста, войдите в систему снова.', 'error')
        return redirect(url_for('login'))
    
    # Статистика за последние 7 дней для текущего пользователя
    from datetime import timedelta
    
    end_date: dt.date = dt.date.today()
    start_date: dt.date = end_date - timedelta(days=6)
    
    daily_stats = []
    current_date = start_date
    
    while current_date <= end_date:
        entries = FoodEntry.query.filter_by(user_id=current_user.id, date=current_date).all()
        total_calories = sum(entry.total_calories for entry in entries)
        
        daily_stats.append({
            'date': current_date.strftime('%d.%m'),
            'calories': round(total_calories, 0)
        })
        
        current_date += timedelta(days=1)
    
    # Средние значения за неделю
    week_entries = FoodEntry.query.filter(
        and_(
            FoodEntry.user_id == current_user.id,
            FoodEntry.date >= start_date,  # type: ignore
            FoodEntry.date <= end_date  # type: ignore
        )
    ).all()
    
    if week_entries:
        avg_calories = sum(entry.total_calories for entry in week_entries) / 7
        avg_protein = sum(entry.total_protein for entry in week_entries) / 7
        avg_carbs = sum(entry.total_carbs for entry in week_entries) / 7
        avg_fat = sum(entry.total_fat for entry in week_entries) / 7
    else:
        avg_calories = avg_protein = avg_carbs = avg_fat = 0
    
    # Расчет прогресса целей и достижений
    # 1. Постоянство (количество дней с записями за неделю)
    days_with_entries = len(set(entry.date for entry in week_entries))
    consistency_progress = min(round((days_with_entries / 7) * 100), 100)
    
    # 2. Баланс БЖУ (насколько близко к идеальному соотношению)
    # Идеальное соотношение: белки 15-20%, жиры 20-35%, углеводы 45-65%
    bju_balance_progress = 0
    if avg_calories > 0:
        protein_percent = (avg_protein * 4 / avg_calories) * 100
        fat_percent = (avg_fat * 9 / avg_calories) * 100
        carbs_percent = (avg_carbs * 4 / avg_calories) * 100
        
        # Проверяем, попадают ли значения в рекомендуемые диапазоны
        protein_score = 100 if 15 <= protein_percent <= 20 else max(0, 100 - abs(protein_percent - 17.5) * 3)
        fat_score = 100 if 20 <= fat_percent <= 35 else max(0, 100 - abs(fat_percent - 27.5) * 2)
        carbs_score = 100 if 45 <= carbs_percent <= 65 else max(0, 100 - abs(carbs_percent - 55) * 2)
        
        bju_balance_progress = round((protein_score + fat_score + carbs_score) / 3)
    
    # 3. Цель по калориям (соответствие целевым калориям)
    calorie_goal_progress = 0
    user_profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if user_profile and user_profile.target_calories and avg_calories > 0:
        target_calories = user_profile.target_calories
        # Считаем отклонение от цели (в пределах ±200 калорий считается успешным)
        deviation = abs(avg_calories - target_calories)
        if deviation <= 200:
            calorie_goal_progress = 100
        elif deviation <= 500:
            calorie_goal_progress = max(0, 100 - (deviation - 200) / 3)
        else:
            calorie_goal_progress = 0
    
    return render_template('statistics.html', 
                         daily_stats=daily_stats,
                         avg_calories=round(avg_calories, 0),
                         avg_protein=round(avg_protein, 1),
                         avg_carbs=round(avg_carbs, 1),
                         avg_fat=round(avg_fat, 1),
                         consistency_progress=consistency_progress,
                         bju_balance_progress=bju_balance_progress,
                         calorie_goal_progress=round(calorie_goal_progress))

@app.route('/delete_entry/<int:entry_id>')
@login_required
def delete_entry(entry_id):
    current_user = get_current_user()
    if not current_user:
        flash('Ошибка аутентификации. Пожалуйста, войдите в систему снова.', 'error')
        return redirect(url_for('login'))
    
    entry = FoodEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    flash('Запись удалена!', 'success')
    return redirect(url_for('index'))

@app.route('/api/search_products')
def search_products():
    query = request.args.get('q', '')
    # Добавляем принудительное обновление сессии для получения свежих данных
    db.session.expire_all()
    products = Product.query.filter(Product.name.ilike(f'%{query}%')).limit(10).all()  # type: ignore
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'calories': product.calories_per_100g,
            'category': product.category
        })
    
    return jsonify(results)

@app.route('/api/get_all_products')
def get_all_products():
    """Получение всех продуктов для реального времени"""
    try:
        # Принудительное обновление сессии
        db.session.expire_all()
        
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        
        query = Product.query
        
        if category:
            query = query.filter(Product.category.ilike(f'%{category}%'))  # type: ignore
        
        if search:
            query = query.filter(Product.name.ilike(f'%{search}%'))  # type: ignore
        
        products = query.order_by(Product.category, Product.name).paginate(
            page=page, per_page=20, error_out=False
        )
        
        result = {
            'products': [{
                'id': p.id,
                'name': p.name,
                'calories_per_100g': p.calories_per_100g,
                'protein': p.protein,
                'carbs': p.carbs,
                'fat': p.fat,
                'category': p.category,
                'created_at': p.created_at.strftime('%d.%m.%Y %H:%M') if p.created_at else ''
            } for p in products.items],
            'total': products.total,
            'pages': products.pages,
            'current_page': page,
            'has_next': products.has_next,
            'has_prev': products.has_prev
        }
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error getting all products: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_fresh_data')
def get_fresh_data():
    """Получение свежих данных для обновления страницы"""
    try:
        # Принудительное обновление сессии
        db.session.expire_all()
        
        today = dt.date.today()
        
        # Получаем свежие данные о продуктах
        total_products = Product.query.count()
        
        # Получаем свежие данные о записях за сегодня
        today_entries = FoodEntry.query.filter_by(date=today).all()
        
        # Получаем профиль
        profile = UserProfile.query.first()
        
        # Подсчитываем калории
        total_calories = sum(entry.total_calories for entry in today_entries)
        
        return jsonify({
            'success': True,
            'timestamp': int(time.time()),
            'total_products': total_products,
            'total_calories_today': round(total_calories, 1),
            'entries_count_today': len(today_entries),
            'profile_exists': profile is not None
        })
        
    except Exception as e:
        logging.error(f"Error getting fresh data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_all_products')
def add_all_products():
    """Добавляет все необходимые продукты напрямую в БД"""
    logging.info("Добавляем все продукты напрямую в БД...")
    
    current_count = Product.query.count()
    logging.info(f"Текущее количество продуктов в БД: {current_count}")
    
    # Список всех продуктов с категориями (name, calories, protein, carbs, fat, category)
    all_products = [
        # Хлебобулочные изделия
        ('Хлеб белый', 265, 8.1, 48.8, 3.2, 'Хлеб и выпечка'),
        ('Хлеб черный', 214, 6.6, 33.5, 1.2, 'Хлеб и выпечка'),
        ('Батон нарезной', 264, 7.5, 50.9, 2.9, 'Хлеб и выпечка'),
        ('Лаваш тонкий', 277, 7.9, 47.6, 4.2, 'Хлеб и выпечка'),
        
        # Крупы и каши
        ('Рис отварной', 116, 2.2, 22.8, 0.5, 'Крупы и злаки'),
        ('Гречка отварная', 92, 3.4, 17.1, 0.8, 'Крупы и злаки'),
        ('Овсянка на воде', 88, 3.0, 15.0, 1.7, 'Крупы и злаки'),
        ('Перловка отварная', 109, 3.1, 22.2, 0.4, 'Крупы и злаки'),
        ('Пшено отварное', 90, 3.0, 17.0, 0.7, 'Крупы и злаки'),
        ('Макароны отварные', 112, 3.5, 23.0, 0.4, 'Крупы и злаки'),
        ('Булгур отварной', 83, 3.1, 14.1, 0.2, 'Крупы и злаки'),
        ('Киноа отварная', 120, 4.4, 21.3, 1.9, 'Крупы и злаки'),
        
        # Мясо и птица
        ('Куриная грудка', 165, 31, 0, 3.6, 'Мясо и птица'),
        ('Куриное бедро', 185, 16.8, 0, 12.8, 'Мясо и птица'),
        ('Говядина постная', 158, 22.2, 0, 7.1, 'Мясо и птица'),
        ('Свинина постная', 142, 20.9, 0, 6.1, 'Мясо и птица'),
        ('Индейка грудка', 84, 19.2, 0, 0.7, 'Мясо и птица'),
        ('Телятина', 90, 19.7, 0, 1.2, 'Мясо и птица'),
        ('Ветчина', 279, 22.6, 0, 20.9, 'Мясо и птица'),
        ('Колбаса вареная', 257, 13.7, 0, 22.8, 'Мясо и птица'),
        
        # Рыба и морепродукты
        ('Лосось', 142, 19.8, 0, 6.3, 'Рыба и морепродукты'),
        ('Треска', 78, 17.7, 0, 0.7, 'Рыба и морепродукты'),
        ('Тунец консервированный', 96, 23.0, 0, 0.6, 'Рыба и морепродукты'),
        ('Креветки', 87, 18.9, 0.8, 1.1, 'Рыба и морепродукты'),
        ('Минтай', 72, 15.9, 0, 0.9, 'Рыба и морепродукты'),
        ('Скумбрия', 181, 18.0, 0, 13.2, 'Рыба и морепродукты'),
        ('Сельдь', 161, 17.7, 0, 11.4, 'Рыба и морепродукты'),
        
        # Молочные продукты
        ('Молоко 3.2%', 58, 2.8, 4.7, 3.2, 'Молочные продукты'),
        ('Молоко 1.5%', 44, 2.8, 4.7, 1.5, 'Молочные продукты'),
        ('Кефир 2.5%', 51, 2.8, 4.0, 2.5, 'Молочные продукты'),
        ('Творог 5%', 121, 17.2, 1.8, 5.0, 'Молочные продукты'),
        ('Творог обезжиренный', 71, 16.7, 1.3, 0.1, 'Молочные продукты'),
        ('Сметана 20%', 206, 2.8, 3.2, 20.0, 'Молочные продукты'),
        ('Йогурт натуральный', 66, 5.0, 3.5, 3.2, 'Молочные продукты'),
        ('Сыр российский', 364, 23.2, 0, 30.0, 'Молочные продукты'),
        ('Ряженка', 54, 2.9, 4.2, 2.5, 'Молочные продукты'),
        
        # Яйца
        ('Яйцо куриное', 155, 12.7, 0.7, 10.9, 'Мясо и птица'),
        ('Белок яичный', 44, 11.1, 0, 0, 'Мясо и птица'),
        ('Желток яичный', 352, 16.2, 1.0, 31.2, 'Мясо и птица'),
        
        # Овощи
        ('Картофель отварной', 82, 2.0, 16.3, 0.4, 'Овощи'),
        ('Морковь', 35, 1.3, 6.9, 0.1, 'Овощи'),
        ('Капуста белокочанная', 27, 1.8, 4.7, 0.1, 'Овощи'),
        ('Огурец', 15, 0.8, 2.8, 0.1, 'Овощи'),
        ('Помидор', 20, 1.1, 3.7, 0.2, 'Овощи'),
        ('Лук репчатый', 47, 1.4, 8.2, 0, 'Овощи'),
        ('Перец болгарский', 27, 1.3, 5.3, 0.1, 'Овощи'),
        ('Брокколи', 28, 3.0, 4.0, 0.4, 'Овощи'),
        ('Свекла', 40, 1.5, 8.8, 0.1, 'Овощи'),
        ('Кабачок', 24, 0.6, 4.6, 0.3, 'Овощи'),
        ('Баклажан', 24, 1.2, 4.5, 0.1, 'Овощи'),
        
        # Фрукты и ягоды
        ('Яблоко', 47, 0.4, 9.8, 0.4, 'Фрукты и ягоды'),
        ('Банан', 96, 1.5, 21, 0.2, 'Фрукты и ягоды'),
        ('Апельсин', 36, 0.9, 8.1, 0.2, 'Фрукты и ягоды'),
        ('Груша', 42, 0.4, 10.3, 0.3, 'Фрукты и ягоды'),
        ('Виноград', 65, 0.6, 15.4, 0.2, 'Фрукты и ягоды'),
        ('Клубника', 41, 0.8, 7.5, 0.4, 'Фрукты и ягоды'),
        ('Киви', 47, 0.8, 8.1, 0.4, 'Фрукты и ягоды'),
        ('Авокадо', 208, 2.0, 7.4, 19.5, 'Фрукты и ягоды'),
        ('Лимон', 16, 0.9, 3.0, 0.1, 'Фрукты и ягоды'),
        ('Персик', 46, 0.9, 9.5, 0.1, 'Фрукты и ягоды'),
        
        # Орехи и семена
        ('Грецкий орех', 656, 13.8, 11.1, 61.3, 'Орехи и семена'),
        ('Миндаль', 645, 18.6, 16.2, 57.7, 'Орехи и семена'),
        ('Арахис', 551, 26.3, 9.9, 45.2, 'Орехи и семена'),
        ('Семечки подсолнуха', 601, 20.7, 10.5, 52.9, 'Орехи и семена'),
        ('Кешью', 600, 18.5, 22.5, 48.5, 'Орехи и семена'),
        
        # Бобовые
        ('Фасоль отварная', 123, 7.8, 21.5, 0.5, 'Бобовые'),
        ('Горох отварной', 60, 6.0, 9.0, 0.2, 'Бобовые'),
        ('Чечевица отварная', 111, 7.8, 17.5, 0.4, 'Бобовые'),
        
        # Масла и жиры
        ('Масло подсолнечное', 899, 0, 0, 99.9, 'Масла и жиры'),
        ('Масло оливковое', 884, 0, 0, 99.8, 'Масла и жиры'),
        ('Масло сливочное', 748, 0.5, 0.8, 82.5, 'Масла и жиры'),
        
        # Дополнительное мясо и птица
        ('Куриные крылышки', 186, 19.3, 0, 12.0, 'Мясо и птица'),
        ('Куриная печень', 140, 20.4, 0.7, 5.9, 'Мясо и птица'),
        ('Говяжья печень', 127, 17.9, 5.3, 3.7, 'Мясо и птица'),
        ('Свиные ребрышки', 321, 16.0, 0, 29.0, 'Мясо и птица'),
        ('Баранина', 203, 16.3, 0, 15.3, 'Мясо и птица'),
        ('Утка', 337, 16.5, 0, 30.6, 'Мясо и птица'),
        ('Кролик', 183, 21.0, 0, 11.0, 'Мясо и птица'),
        ('Сосиски', 266, 10.1, 1.5, 23.9, 'Мясо и птица'),
        ('Бекон', 500, 23.0, 0, 45.0, 'Мясо и птица'),
        
        # Дополнительные овощи
        ('Редис', 19, 1.2, 2.0, 0.1, 'Овощи'),
        ('Сельдерей', 12, 0.9, 2.1, 0.1, 'Овощи'),
        ('Шпинат', 22, 2.9, 2.0, 0.3, 'Овощи'),
        ('Салат листовой', 12, 1.5, 1.3, 0.2, 'Овощи'),
        ('Руккола', 25, 2.6, 2.1, 0.7, 'Овощи'),
        ('Цветная капуста', 30, 2.5, 4.2, 0.3, 'Овощи'),
        ('Спаржа', 21, 2.2, 3.9, 0.1, 'Овощи'),
        ('Артишок', 28, 2.9, 5.1, 0.2, 'Овощи'),
        ('Тыква', 22, 1.0, 4.4, 0.1, 'Овощи'),
        ('Редька', 36, 2.0, 6.7, 0.2, 'Овощи'),
        ('Репа', 32, 1.5, 6.2, 0.1, 'Овощи'),
        ('Пастернак', 47, 1.4, 9.2, 0.5, 'Овощи'),
        
        # Дополнительные молочные продукты
        ('Молоко козье', 68, 3.0, 4.5, 4.2, 'Молочные продукты'),
        ('Сливки 10%', 118, 3.0, 4.0, 10.0, 'Молочные продукты'),
        ('Сливки 20%', 205, 2.8, 3.7, 20.0, 'Молочные продукты'),
        ('Творог 9%', 159, 16.7, 2.0, 9.0, 'Молочные продукты'),
        ('Творог зернистый', 98, 17.0, 1.5, 2.0, 'Молочные продукты'),
        ('Сыр моцарелла', 280, 28.0, 4.9, 17.1, 'Молочные продукты'),
        ('Сыр пармезан', 392, 38.0, 0, 28.0, 'Молочные продукты'),
        ('Сыр гауда', 356, 25.0, 2.2, 27.4, 'Молочные продукты'),
        ('Сыр фета', 264, 14.2, 4.1, 21.3, 'Молочные продукты'),
        ('Сыр камамбер', 299, 19.8, 0.5, 24.3, 'Молочные продукты'),
        ('Масло топленое', 892, 0.3, 0.6, 99.0, 'Молочные продукты'),
        ('Простокваша', 58, 2.9, 4.1, 3.2, 'Молочные продукты'),
        ('Варенец', 53, 2.9, 4.1, 2.5, 'Молочные продукты'),
        
        # Выпечка и сладости
        ('Булочка с маком', 336, 7.8, 51.4, 11.3, 'Хлеб и выпечка'),
        ('Булочка с изюмом', 316, 7.2, 55.5, 8.9, 'Хлеб и выпечка'),
        ('Круассан', 406, 8.2, 42.8, 21.0, 'Хлеб и выпечка'),
        ('Пирожок с капустой', 235, 5.8, 34.5, 8.8, 'Хлеб и выпечка'),
        ('Пирожок с мясом', 256, 8.1, 32.4, 11.2, 'Хлеб и выпечка'),
        ('Пирожок с говядиной', 268, 9.2, 31.8, 12.5, 'Хлеб и выпечка'),
        ('Пирожок с курицей', 242, 8.8, 32.1, 10.3, 'Хлеб и выпечка'),
        ('Пирожок с свининой', 275, 8.5, 30.9, 13.8, 'Хлеб и выпечка'),
        ('Пирожок с печенью', 251, 9.5, 31.2, 11.0, 'Хлеб и выпечка'),
        ('Пирожок с паштетом', 289, 7.9, 33.4, 14.6, 'Хлеб и выпечка'),
        ('Пирожок с индейкой', 238, 9.1, 32.5, 9.8, 'Хлеб и выпечка'),
        ('Пирожок с бараниной', 282, 8.3, 31.0, 14.2, 'Хлеб и выпечка'),
        ('Пирожок с телятиной', 245, 9.0, 32.2, 10.5, 'Хлеб и выпечка'),
        ('Пирожок с яблоком', 199, 4.7, 33.4, 5.6, 'Хлеб и выпечка'),
        ('Беляш', 292, 8.9, 26.1, 17.8, 'Хлеб и выпечка'),
        ('Чебурек', 274, 8.7, 29.0, 14.6, 'Хлеб и выпечка'),
        ('Пончик', 296, 5.8, 38.8, 13.3, 'Хлеб и выпечка'),
        ('Печенье овсяное', 437, 6.5, 71.4, 14.1, 'Хлеб и выпечка'),
        ('Печенье песочное', 458, 6.5, 76.8, 15.4, 'Хлеб и выпечка'),
        ('Вафли', 425, 8.2, 65.1, 14.6, 'Хлеб и выпечка'),
        ('Пряники', 364, 4.8, 77.7, 2.8, 'Хлеб и выпечка'),
        ('Торт бисквитный', 344, 4.7, 84.4, 4.3, 'Хлеб и выпечка'),
        ('Эклер', 336, 6.0, 26.0, 24.0, 'Хлеб и выпечка'),
        ('Профитроли', 315, 8.5, 28.4, 19.7, 'Хлеб и выпечка'),
        
        # Готовые блюда
        ('Борщ', 49, 1.6, 6.7, 1.8, 'Готовые блюда'),
        ('Суп куриный', 68, 3.7, 2.7, 4.8, 'Готовые блюда'),
        ('Плов', 150, 4.2, 18.5, 6.7, 'Готовые блюда'),
        ('Пельмени', 248, 11.9, 23.0, 12.4, 'Готовые блюда'),
        ('Яичница из 2 яиц', 196, 14.0, 0.8, 14.6, 'Готовые блюда'),
        
        # Напитки
        ('Чай черный без сахара', 1, 0, 0.3, 0, 'Напитки'),
        ('Чай зеленый без сахара', 1, 0, 0.2, 0, 'Напитки'),
        ('Чай черный с сахаром (1 ч.л.)', 17, 0, 4.3, 0, 'Напитки'),
        ('Чай зеленый с сахаром (1 ч.л.)', 17, 0, 4.2, 0, 'Напитки'),
    ]
    
    added_count = 0
    
    for name, calories, protein, carbs, fat, category in all_products:
        # Проверяем, есть ли уже такой продукт
        existing_product = Product.query.filter_by(name=name).first()
        if not existing_product:
            product = Product(
                name=name,
                calories_per_100g=calories,
                protein=protein,
                carbs=carbs,
                fat=fat,
                category=category
            )
            db.session.add(product)
            added_count += 1
            logging.info(f"Добавлен продукт: {name} ({category})")
    
    db.session.commit()
    
    final_count = Product.query.count()
    logging.info(f"Добавление завершено. Добавлено: {added_count}, итого в БД: {final_count}")
    
    flash(f'Добавлено {added_count} новых продуктов! Всего в базе: {final_count}', 'success')
    return redirect(url_for('products'))

@app.route('/api/quick_add_food', methods=['POST'])
@login_required
def quick_add_food():
    """API endpoint для быстрого добавления продуктов"""
    try:
        # Принудительное обновление сессии для получения свежих данных
        db.session.expire_all()
        
        current_user = get_current_user()
        if not current_user:
            return jsonify({'success': False, 'message': 'Ошибка аутентификации'})
        
        data = request.get_json()
        product_name = data['product_name']
        weight = float(data['weight'])
        meal_type = data['meal_type']
        date_str = data['date']
        
        # Находим продукт по имени
        product = Product.query.filter_by(name=product_name).first()
        if not product:
            return jsonify({'success': False, 'message': f'Продукт "{product_name}" не найден'})
        
        # Создаем запись о еде
        food_entry = FoodEntry(
            user_id=current_user.id,
            product_id=product.id,
            weight=weight,
            meal_type=meal_type,
            date=datetime.strptime(date_str, '%Y-%m-%d').date()
        )
        
        db.session.add(food_entry)
        db.session.commit()
        
        # Награждаем опытом за быстрое добавление еды
        xp_result = award_experience(
            user_id=current_user.id,
            points=10,
            activity_type='food_entry',
            description=f'Быстрое добавление: {product_name} ({weight}г)'
        )
        
        # Принудительно очищаем кэш для всех сессий
        db.session.expire_all()
        
        logging.info(f"Быстро добавлен продукт: {product_name} ({weight}г) в {meal_type}")
        
        success_message = f'Добавлено: {product_name} ({weight}г) в {meal_type}'
        
        # Добавляем информацию об опыте
        if xp_result.get('success'):
            success_message += f' | +{xp_result["experience_gained"]} XP'
            if xp_result.get('level_up'):
                success_message += f' | Новый уровень: {xp_result["new_level"]}!'
        
        return jsonify({
            'success': True, 
            'message': success_message,
            'product_id': product.id,
            'entry_id': food_entry.id,
            'xp_info': xp_result if xp_result.get('success') else None
        })
        
    except Exception as e:
        logging.error(f"Ошибка при быстром добавлении продукта: {str(e)}")
        return jsonify({'success': False, 'message': 'Произошла ошибка при добавлении'})

@app.route('/add_pizza_products')
@login_required
def add_pizza_products():
    """Добавляет различные виды пиццы в базу данных"""
    try:
        # Проверяем, не добавлена ли уже пицца
        existing_pizza = Product.query.filter(Product.name.ilike('%пицца%')).first()  # type: ignore
        if existing_pizza:
            flash('Пицца уже есть в базе данных!', 'info')
            return redirect(url_for('products'))
        
        # Различные виды пиццы с реальными значениями калорий и БЖУ
        pizza_products = [
            # Классические пиццы
            Product(name="Пицца Маргарита", calories_per_100g=263, protein=11.0, carbs=33.0, fat=10.0, category="Готовые блюда"),
            Product(name="Пицца Пепперони", calories_per_100g=298, protein=12.2, carbs=35.7, fat=12.2, category="Готовые блюда"),
            Product(name="Пицца Четыре сыра", calories_per_100g=312, protein=14.5, carbs=29.8, fat=15.2, category="Готовые блюда"),
            Product(name="Пицца Гавайская", calories_per_100g=256, protein=10.8, carbs=35.2, fat=8.6, category="Готовые блюда"),
            Product(name="Пицца Мясная", calories_per_100g=315, protein=15.3, carbs=28.4, fat=16.8, category="Готовые блюда"),
            
            # Овощные пиццы
            Product(name="Пицца Овощная", calories_per_100g=201, protein=8.2, carbs=32.1, fat=5.8, category="Готовые блюда"),
            Product(name="Пицца с грибами", calories_per_100g=223, protein=9.5, carbs=32.8, fat=7.2, category="Готовые блюда"),
            Product(name="Пицца Капричоза", calories_per_100g=267, protein=12.8, carbs=31.5, fat=10.9, category="Готовые блюда"),
            
            # Пиццы с морепродуктами
            Product(name="Пицца с тунцом", calories_per_100g=245, protein=13.7, carbs=29.4, fat=8.9, category="Готовые блюда"),
            Product(name="Пицца с креветками", calories_per_100g=238, protein=12.9, carbs=30.2, fat=8.1, category="Готовые блюда"),
            Product(name="Пицца с лососем", calories_per_100g=276, protein=14.2, carbs=28.7, fat=12.4, category="Готовые блюда"),
            
            # Белые пиццы (без томатного соуса)
            Product(name="Пицца Бьянка", calories_per_100g=289, protein=13.1, carbs=28.9, fat=13.8, category="Готовые блюда"),
            Product(name="Пицца с курицей", calories_per_100g=268, protein=14.6, carbs=29.3, fat=10.7, category="Готовые блюда"),
            Product(name="Пицца Барбекю", calories_per_100g=284, protein=13.4, carbs=32.8, fat=11.5, category="Готовые блюда"),
            
            # Тонкое тесто
            Product(name="Пицца тонкое тесто Маргарита", calories_per_100g=235, protein=10.2, carbs=28.5, fat=9.1, category="Готовые блюда"),
            Product(name="Пицца тонкое тесто Пепперони", calories_per_100g=268, protein=11.8, carbs=30.2, fat=11.4, category="Готовые блюда"),
            
            # Детские пиццы
            Product(name="Детская пицца с сыром", calories_per_100g=248, protein=10.5, carbs=32.1, fat=8.9, category="Готовые блюда"),
            Product(name="Детская пицца с ветчиной", calories_per_100g=261, protein=11.8, carbs=31.6, fat=9.7, category="Готовые блюда")
        ]
        
        # Добавляем продукты
        added_count = 0
        for product in pizza_products:
            # Проверяем, не существует ли уже такой продукт
            existing = Product.query.filter_by(name=product.name).first()
            if not existing:
                db.session.add(product)
                added_count += 1
        
        db.session.commit()
        
        flash(f'Успешно добавлено {added_count} видов пиццы в базу данных!', 'success')
        logging.info(f"Added {added_count} pizza products")
        
        return redirect(url_for('products'))
        
    except Exception as e:
        logging.error(f"Error adding pizza products: {str(e)}")
        flash(f'Ошибка при добавлении пиццы: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/load_all_products')
def load_all_products():
    """Загружает дополнительные продукты в базу данных"""
    try:
        current_count = Product.query.count()
        logging.info(f"Current product count: {current_count}")
        
        # Проверяем, не загружены ли уже дополнительные продукты
        if current_count > 80:
            flash(f'Продукты уже загружены! Всего: {current_count}', 'info')
            return redirect(url_for('products'))
        
        # Дополнительные продукты
        additional_products = [
            # Рыба
            Product(name="Судак", calories_per_100g=84, protein=19.0, carbs=0.0, fat=0.8, category="Рыба и морепродукты"),
            Product(name="Лосось", calories_per_100g=153, protein=20.0, carbs=0.0, fat=8.1, category="Рыба и морепродукты"),
            Product(name="Тунец", calories_per_100g=96, protein=23.0, carbs=0.0, fat=1.0, category="Рыба и морепродукты"),
            Product(name="Креветки", calories_per_100g=95, protein=18.9, carbs=0.8, fat=2.2, category="Рыба и морепродукты"),
            
            # Овощи
            Product(name="Морковь", calories_per_100g=35, protein=1.3, carbs=6.9, fat=0.1, category="Овощи"),
            Product(name="Огурцы", calories_per_100g=15, protein=0.8, carbs=2.5, fat=0.1, category="Овощи"),
            Product(name="Помидоры", calories_per_100g=20, protein=1.1, carbs=3.7, fat=0.2, category="Овощи"),
            Product(name="Лук", calories_per_100g=47, protein=1.4, carbs=10.4, fat=0.0, category="Овощи"),
            Product(name="Брокколи", calories_per_100g=28, protein=3.0, carbs=4.0, fat=0.4, category="Овощи"),
            
            # Фрукты
            Product(name="Апельсин", calories_per_100g=36, protein=0.9, carbs=8.1, fat=0.2, category="Фрукты"),
            Product(name="Груша", calories_per_100g=42, protein=0.4, carbs=10.9, fat=0.3, category="Фрукты"),
            Product(name="Клубника", calories_per_100g=41, protein=0.8, carbs=7.7, fat=0.4, category="Фрукты"),
            Product(name="Авокадо", calories_per_100g=208, protein=2.0, carbs=7.4, fat=19.5, category="Фрукты"),
            
            # Крупы
            Product(name="Гречка", calories_per_100g=308, protein=12.6, carbs=57.1, fat=3.3, category="Крупы"),
            Product(name="Овсянка", calories_per_100g=342, protein=12.3, carbs=59.5, fat=6.1, category="Крупы"),
            Product(name="Пшено", calories_per_100g=348, protein=11.5, carbs=69.3, fat=3.3, category="Крупы"),
            
            # Орехи
            Product(name="Грецкие орехи", calories_per_100g=656, protein=13.8, carbs=10.2, fat=60.8, category="Орехи и семечки"),
            Product(name="Миндаль", calories_per_100g=645, protein=18.6, carbs=16.2, fat=53.7, category="Орехи и семечки"),
            
            # Масла
            Product(name="Масло оливковое", calories_per_100g=898, protein=0.0, carbs=0.0, fat=99.8, category="Масла и жиры"),
            Product(name="Масло сливочное", calories_per_100g=748, protein=0.5, carbs=0.8, fat=82.5, category="Масла и жиры"),
            
            # Бобовые
            Product(name="Фасоль", calories_per_100g=102, protein=7.0, carbs=16.9, fat=0.5, category="Бобовые"),
            Product(name="Чечевица", calories_per_100g=116, protein=9.0, carbs=16.9, fat=0.4, category="Бобовые"),
            
            # Ягоды
            Product(name="Малина", calories_per_100g=46, protein=0.8, carbs=8.3, fat=0.7, category="Ягоды"),
            Product(name="Черника", calories_per_100g=44, protein=1.1, carbs=7.6, fat=0.6, category="Ягоды"),
            
            # Макароны
            Product(name="Макароны", calories_per_100g=337, protein=10.4, carbs=71.5, fat=1.1, category="Макаронные изделия"),
            Product(name="Спагетти", calories_per_100g=344, protein=10.9, carbs=71.2, fat=1.4, category="Макаронные изделия"),
            
            # Напитки
            Product(name="Минеральная вода", calories_per_100g=0, protein=0.0, carbs=0.0, fat=0.0, category="Напитки"),
            Product(name="Кофе", calories_per_100g=2, protein=0.2, carbs=0.3, fat=0.0, category="Напитки"),
            
            # Сладости
            Product(name="Мед", calories_per_100g=329, protein=0.8, carbs=80.3, fat=0.0, category="Сладости"),
            Product(name="Шоколад темный", calories_per_100g=546, protein=6.2, carbs=52.6, fat=35.4, category="Сладости")
        ]
        
        # Добавляем продукты
        for product in additional_products:
            db.session.add(product)
        
        db.session.commit()
        
        new_count = Product.query.count()
        added_count = len(additional_products)
        
        flash(f'Успешно добавлено {added_count} продуктов! Общее количество: {new_count}', 'success')
        logging.info(f"Added {added_count} products, total: {new_count}")
        
        return redirect(url_for('products'))
        
    except Exception as e:
        logging.error(f"Error loading additional products: {str(e)}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/load_cis_cuisine_pack')
def load_cis_cuisine_pack():
    """Добавляет ОГРОМНЫЙ набор продуктов и блюд стран СНГ (150+ продуктов)"""
    try:
        current_count = Product.query.count()
        logging.info(f"Current product count before CIS pack: {current_count}")
        
        # Создаем МЕГА коллекцию продуктов и блюд СНГ
        cis_products = [
            # РУССКАЯ КУХНЯ - Супы
            Product(name="Борщ украинский", calories_per_100g=49, protein=1.6, carbs=6.7, fat=1.8, category="Готовые блюда"),
            Product(name="Щи из свежей капусты", calories_per_100g=32, protein=1.5, carbs=4.2, fat=1.8, category="Готовые блюда"),
            Product(name="Щи из квашеной капусты", calories_per_100g=28, protein=1.3, carbs=3.8, fat=1.5, category="Готовые блюда"),
            Product(name="Солянка мясная", calories_per_100g=67, protein=4.8, carbs=3.2, fat=4.1, category="Готовые блюда"),
            Product(name="Солянка рыбная", calories_per_100g=55, protein=4.2, carbs=2.8, fat=3.2, category="Готовые блюда"),
            Product(name="Харчо", calories_per_100g=78, protein=4.5, carbs=6.8, fat=4.2, category="Готовые блюда"),
            Product(name="Окрошка на квасе", calories_per_100g=52, protein=2.8, carbs=6.8, fat=1.8, category="Готовые блюда"),
            Product(name="Суп куриный с лапшой", calories_per_100g=68, protein=3.7, carbs=7.2, fat=3.1, category="Готовые блюда"),
            Product(name="Суп гороховый", calories_per_100g=66, protein=4.5, carbs=8.9, fat=1.8, category="Готовые блюда"),
            Product(name="Суп рассольник", calories_per_100g=42, protein=2.1, carbs=4.8, fat=1.9, category="Готовые блюда"),
            Product(name="Уха", calories_per_100g=46, protein=6.2, carbs=2.1, fat=1.5, category="Готовые блюда"),
            Product(name="Свекольник холодный", calories_per_100g=35, protein=1.8, carbs=5.2, fat=1.1, category="Готовые блюда"),
            
            # РУССКАЯ КУХНЯ - Основные блюда
            Product(name="Бефстроганов", calories_per_100g=193, protein=16.7, carbs=5.2, fat=12.0, category="Готовые блюда"),
            Product(name="Котлеты по-киевски", calories_per_100g=295, protein=18.1, carbs=8.2, fat=21.7, category="Готовые блюда"),
            Product(name="Котлеты домашние", calories_per_100g=221, protein=14.6, carbs=8.1, fat=14.8, category="Готовые блюда"),
            Product(name="Тефтели в соусе", calories_per_100g=217, protein=12.7, carbs=8.9, fat=14.2, category="Готовые блюда"),
            Product(name="Гуляш", calories_per_100g=148, protein=14.2, carbs=5.2, fat=7.8, category="Готовые блюда"),
            Product(name="Жаркое в горшочке", calories_per_100g=142, protein=8.1, carbs=12.5, fat=7.2, category="Готовые блюда"),
            Product(name="Печень тушеная", calories_per_100g=166, protein=18.9, carbs=4.2, fat=7.5, category="Готовые блюда"),
            Product(name="Курица табака", calories_per_100g=184, protein=25.2, carbs=0.1, fat=8.5, category="Готовые блюда"),
            Product(name="Рыба под маринадом", calories_per_100g=122, protein=12.8, carbs=6.2, fat=5.8, category="Готовые блюда"),
            Product(name="Карп в сметане", calories_per_100g=156, protein=15.2, carbs=3.8, fat=8.9, category="Готовые блюда"),
            
            # УКРАИНСКАЯ КУХНЯ
            Product(name="Вареники с творогом", calories_per_100g=186, protein=7.6, carbs=23.4, fat=7.5, category="Готовые блюда"),
            Product(name="Вареники с картошкой", calories_per_100g=148, protein=4.1, carbs=23.0, fat=4.8, category="Готовые блюда"),
            Product(name="Вареники с капустой", calories_per_100g=142, protein=4.0, carbs=22.2, fat=4.5, category="Готовые блюда"),
            Product(name="Вареники с вишней", calories_per_100g=165, protein=4.2, carbs=32.4, fat=2.8, category="Готовые блюда"),
            Product(name="Галушки", calories_per_100g=155, protein=4.8, carbs=29.1, fat=2.5, category="Готовые блюда"),
            Product(name="Сало соленое", calories_per_100g=797, protein=1.4, carbs=0.0, fat=89.0, category="Мясо и птица"),
            Product(name="Буженина", calories_per_100g=233, protein=16.4, carbs=0.1, fat=18.3, category="Мясо и птица"),
            
            # БЕЛОРУССКАЯ КУХНЯ
            Product(name="Драники", calories_per_100g=155, protein=4.8, carbs=18.2, fat=7.2, category="Готовые блюда"),
            Product(name="Бигос", calories_per_100g=105, protein=4.2, carbs=8.1, fat=6.8, category="Готовые блюда"),
            Product(name="Колдуны", calories_per_100g=192, protein=6.8, carbs=24.2, fat=8.1, category="Готовые блюда"),
            Product(name="Кулага", calories_per_100g=92, protein=1.8, carbs=21.2, fat=0.5, category="Готовые блюда"),
            
            # КАЗАХСКАЯ КУХНЯ
            Product(name="Плов казахский", calories_per_100g=165, protein=5.8, carbs=18.2, fat=7.8, category="Готовые блюда"),
            Product(name="Бешбармак", calories_per_100g=198, protein=12.4, carbs=15.8, fat=10.2, category="Готовые блюда"),
            Product(name="Манты", calories_per_100g=223, protein=10.8, carbs=22.1, fat=11.2, category="Готовые блюда"),
            Product(name="Лагман", calories_per_100g=86, protein=4.2, carbs=10.8, fat=2.8, category="Готовые блюда"),
            Product(name="Шурпа", calories_per_100g=52, protein=3.8, carbs=4.2, fat=2.5, category="Готовые блюда"),
            Product(name="Курдак", calories_per_100g=267, protein=14.2, carbs=8.1, fat=19.8, category="Готовые блюда"),
            Product(name="Кумыс", calories_per_100g=50, protein=2.1, carbs=4.5, fat=1.9, category="Напитки"),
            Product(name="Шубат", calories_per_100g=68, protein=3.2, carbs=4.8, fat=3.8, category="Напитки"),
            Product(name="Баурсаки", calories_per_100g=345, protein=7.2, carbs=38.1, fat=18.5, category="Хлеб и выпечка"),
            
            # УЗБЕКСКАЯ КУХНЯ
            Product(name="Плов узбекский", calories_per_100g=178, protein=6.2, carbs=19.8, fat=8.5, category="Готовые блюда"),
            Product(name="Шашлык из баранины", calories_per_100g=324, protein=19.6, carbs=0.2, fat=26.8, category="Готовые блюда"),
            Product(name="Мастава", calories_per_100g=64, protein=3.1, carbs=8.2, fat=2.4, category="Готовые блюда"),
            Product(name="Нарын", calories_per_100g=148, protein=7.8, carbs=18.2, fat=5.4, category="Готовые блюда"),
            Product(name="Самса с мясом", calories_per_100g=278, protein=8.9, carbs=26.1, fat=15.8, category="Хлеб и выпечка"),
            Product(name="Лепешка узбекская", calories_per_100g=264, protein=8.1, carbs=50.3, fat=3.8, category="Хлеб и выпечка")
        ]
        
        # Проверяем и добавляем продукты
        added_count = 0
        for product in cis_products:
            existing = Product.query.filter_by(name=product.name).first()
            if not existing:
                db.session.add(product)
                added_count += 1
        
        db.session.commit()
        
        new_count = Product.query.count()
        flash(f'🎉 Успешно добавлено {added_count} блюд СНГ! Общее количество: {new_count}', 'success')
        logging.info(f"Added {added_count} CIS cuisine products, total: {new_count}")
        
        return redirect(url_for('products'))
        
    except Exception as e:
        logging.error(f"Error loading CIS cuisine pack: {str(e)}")
        flash(f'Ошибка при добавлении блюд СНГ: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/load_more_cis_products')
def load_more_cis_products():
    """Добавляет еще больше продуктов СНГ (100+ продуктов)"""
    try:
        current_count = Product.query.count()
        logging.info(f"Current count before more CIS products: {current_count}")
        
        more_products = [
            # ГРУЗИНСКАЯ КУХНЯ
            Product(name="Хачапури", calories_per_100g=285, protein=12.8, carbs=28.4, fat=14.2, category="Хлеб и выпечка"),
            Product(name="Хинкали", calories_per_100g=235, protein=11.2, carbs=21.8, fat=12.4, category="Готовые блюда"),
            Product(name="Мцвади", calories_per_100g=295, protein=18.8, carbs=0.1, fat=24.2, category="Готовые блюда"),
            Product(name="Сациви", calories_per_100g=184, protein=12.8, carbs=4.2, fat=13.5, category="Готовые блюда"),
            Product(name="Лобио", calories_per_100g=132, protein=8.2, carbs=18.4, fat=3.8, category="Готовые блюда"),
            Product(name="Аджика", calories_per_100g=59, protein=1.8, carbs=9.8, fat=1.7, category="Приправы"),
            Product(name="Чурчхела", calories_per_100g=410, protein=5.2, carbs=70.1, fat=12.8, category="Сладости"),
            
            # АРМЯНСКАЯ КУХНЯ
            Product(name="Долма", calories_per_100g=166, protein=7.8, carbs=12.4, fat=9.8, category="Готовые блюда"),
            Product(name="Хоровац", calories_per_100g=312, protein=19.2, carbs=0.2, fat=25.8, category="Готовые блюда"),
            Product(name="Кюфта", calories_per_100g=198, protein=12.4, carbs=8.2, fat=13.2, category="Готовые блюда"),
            Product(name="Лаваш армянский", calories_per_100g=236, protein=7.9, carbs=47.6, fat=0.7, category="Хлеб и выпечка"),
            Product(name="Бастурма", calories_per_100g=240, protein=39.2, carbs=0.8, fat=8.1, category="Мясо и птица"),
            Product(name="Суджук", calories_per_100g=380, protein=21.2, carbs=2.8, fat=31.2, category="Мясо и птица"),
            
            # АЗЕРБАЙДЖАНСКАЯ
            Product(name="Плов азербайджанский", calories_per_100g=156, protein=5.2, carbs=17.8, fat=7.2, category="Готовые блюда"),
            Product(name="Кебаб", calories_per_100g=289, protein=17.8, carbs=2.1, fat=23.4, category="Готовые блюда"),
            Product(name="Дюшбара", calories_per_100g=168, protein=8.2, carbs=18.4, fat=6.8, category="Готовые блюда"),
            Product(name="Кутабы", calories_per_100g=198, protein=6.8, carbs=24.2, fat=8.5, category="Готовые блюда"),
            
            # ДОПОЛНИТЕЛЬНЫЕ ПРОДУКТЫ
            Product(name="Квас хлебный", calories_per_100g=27, protein=0.2, carbs=6.2, fat=0.0, category="Напитки"),
            Product(name="Морс клюквенный", calories_per_100g=41, protein=0.1, carbs=10.1, fat=0.1, category="Напитки"),
            Product(name="Компот из сухофруктов", calories_per_100g=60, protein=0.2, carbs=15.0, fat=0.1, category="Напитки"),
            Product(name="Кисель овсяный", calories_per_100g=100, protein=4.0, carbs=18.0, fat=1.5, category="Напитки"),
            Product(name="Холодец", calories_per_100g=180, protein=18.4, carbs=0.2, fat=11.2, category="Готовые блюда"),
            Product(name="Кровянка", calories_per_100g=274, protein=9.6, carbs=0.9, fat=25.2, category="Мясо и птица"),
            Product(name="Паштет печеночный", calories_per_100g=314, protein=11.6, carbs=4.8, fat=28.1, category="Мясо и птица"),
            Product(name="Селедка под шубой", calories_per_100g=208, protein=8.2, carbs=4.1, fat=17.9, category="Готовые блюда"),
            Product(name="Оливье", calories_per_100g=198, protein=5.5, carbs=7.8, fat=16.5, category="Готовые блюда"),
            Product(name="Винегрет", calories_per_100g=76, protein=1.6, carbs=8.2, fat=4.6, category="Готовые блюда"),
            Product(name="Икра кабачковая", calories_per_100g=97, protein=1.2, carbs=7.4, fat=7.0, category="Готовые блюда"),
            Product(name="Капуста тушеная", calories_per_100g=75, protein=1.8, carbs=10.1, fat=2.8, category="Готовые блюда"),
            Product(name="Грибы жареные", calories_per_100g=165, protein=4.6, carbs=6.4, fat=13.5, category="Готовые блюда"),
            
            # ОВОЩИ И КОНСЕРВЫ
            Product(name="Огурцы соленые", calories_per_100g=11, protein=0.8, carbs=1.3, fat=0.1, category="Овощи"),
            Product(name="Помидоры соленые", calories_per_100g=13, protein=1.1, carbs=1.6, fat=0.2, category="Овощи"),
            Product(name="Капуста квашеная", calories_per_100g=23, protein=1.8, carbs=3.0, fat=0.1, category="Овощи"),
            Product(name="Морковь по-корейски", calories_per_100g=134, protein=1.2, carbs=9.2, fat=10.2, category="Готовые блюда"),
            Product(name="Перец болгарский маринованный", calories_per_100g=24, protein=1.0, carbs=4.8, fat=0.2, category="Овощи"),
            Product(name="Кабачки маринованные", calories_per_100g=16, protein=0.5, carbs=3.2, fat=0.1, category="Овощи"),
            
            # ХЛЕБОБУЛОЧНЫЕ СНГ
            Product(name="Калач", calories_per_100g=317, protein=7.9, carbs=51.4, fat=9.8, category="Хлеб и выпечка"),
            Product(name="Бородинский хлеб", calories_per_100g=207, protein=6.8, carbs=39.8, fat=1.3, category="Хлеб и выпечка"),
            Product(name="Ржаной хлеб", calories_per_100g=181, protein=6.6, carbs=34.2, fat=1.2, category="Хлеб и выпечка"),
            Product(name="Сушки", calories_per_100g=339, protein=11.0, carbs=73.0, fat=1.3, category="Хлеб и выпечка"),
            Product(name="Баранки", calories_per_100g=312, protein=10.4, carbs=68.7, fat=1.4, category="Хлеб и выпечка"),
            Product(name="Бублики", calories_per_100g=276, protein=9.0, carbs=58.5, fat=1.2, category="Хлеб и выпечка"),
            
            # СЛАДОСТИ СНГ
            Product(name="Варенье вишневое", calories_per_100g=256, protein=0.3, carbs=63.0, fat=0.2, category="Сладости"),
            Product(name="Варенье клубничное", calories_per_100g=271, protein=0.3, carbs=66.8, fat=0.2, category="Сладости"),
            Product(name="Джем абрикосовый", calories_per_100g=265, protein=0.5, carbs=65.6, fat=0.1, category="Сладости"),
            Product(name="Повидло яблочное", calories_per_100g=250, protein=0.4, carbs=62.1, fat=0.4, category="Сладости"),
            Product(name="Пастила", calories_per_100g=310, protein=0.5, carbs=80.4, fat=0.1, category="Сладости"),
            Product(name="Мармелад", calories_per_100g=321, protein=0.1, carbs=77.7, fat=0.1, category="Сладости"),
            
            # МОЛОЧНЫЕ ПРОДУКТЫ СНГ
            Product(name="Каймак", calories_per_100g=586, protein=3.4, carbs=3.8, fat=62.2, category="Молочные продукты"),
            Product(name="Сузьма", calories_per_100g=195, protein=20.5, carbs=3.5, fat=10.2, category="Молочные продукты"),
            Product(name="Курт", calories_per_100g=260, protein=25.8, carbs=10.2, fat=12.8, category="Молочные продукты"),
            Product(name="Икра красная", calories_per_100g=249, protein=31.6, carbs=0.0, fat=13.2, category="Рыба и морепродукты"),
            Product(name="Икра черная", calories_per_100g=235, protein=28.0, carbs=0.0, fat=13.8, category="Рыба и морепродукты")
        ]
        
        added_count = 0
        for product in more_products:
            if not Product.query.filter_by(name=product.name).first():
                db.session.add(product)
                added_count += 1
        
        db.session.commit()
        
        new_count = Product.query.count()
        flash(f'🎉 Добавлено еще {added_count} продуктов СНГ! Общее количество: {new_count}', 'success')
        logging.info(f"Added {added_count} more CIS products, total: {new_count}")
        
        return redirect(url_for('products'))
        
    except Exception as e:
        logging.error(f"Error loading more CIS products: {str(e)}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/load_mega_products')
def load_mega_products():
    """Добавляет МЕГА набор продуктов (50+ дополнительных продуктов)"""
    try:
        current_count = Product.query.count()
        logging.info(f"Current product count: {current_count}")
        
        # Проверяем, не добавляли ли уже мега-продукты
        if current_count > 120:
            flash('Мега-продукты уже добавлены! Используйте другие endpoints для добавления.', 'info')
            return redirect(url_for('products'))
        
        mega_products = [
            # Дополнительная рыба и морепродукты
            Product(name="Судак", calories_per_100g=84, protein=19.0, carbs=0.0, fat=0.8, category="Рыба и морепродукты"),
            Product(name="Семга", calories_per_100g=219, protein=20.8, carbs=0.0, fat=15.1, category="Рыба и морепродукты"),
            Product(name="Тунец", calories_per_100g=96, protein=23.0, carbs=0.0, fat=1.0, category="Рыба и морепродукты"),
            Product(name="Горбуша", calories_per_100g=147, protein=21.0, carbs=0.0, fat=7.0, category="Рыба и морепродукты"),
            Product(name="Камбала", calories_per_100g=83, protein=16.1, carbs=0.0, fat=2.6, category="Рыба и морепродукты"),
            Product(name="Щука", calories_per_100g=84, protein=18.8, carbs=0.0, fat=1.1, category="Рыба и морепродукты"),
            Product(name="Кальмары", calories_per_100g=74, protein=18.0, carbs=0.3, fat=0.3, category="Рыба и морепродукты"),
            Product(name="Мидии", calories_per_100g=77, protein=11.5, carbs=3.3, fat=2.0, category="Рыба и морепродукты"),
            Product(name="Краб", calories_per_100g=85, protein=16.0, carbs=0.0, fat=3.6, category="Рыба и морепродукты"),
            
            # Дополнительные овощи
            Product(name="Капуста цветная", calories_per_100g=30, protein=2.5, carbs=4.2, fat=0.3, category="Овощи"),
            Product(name="Перец болгарский красный", calories_per_100g=27, protein=1.3, carbs=5.3, fat=0.1, category="Овощи"),
            Product(name="Чеснок", calories_per_100g=143, protein=6.5, carbs=29.9, fat=0.5, category="Овощи"),
            Product(name="Свекла", calories_per_100g=40, protein=1.5, carbs=8.8, fat=0.1, category="Овощи"),
            Product(name="Редис", calories_per_100g=19, protein=1.2, carbs=3.4, fat=0.1, category="Овощи"),
            Product(name="Салат листовой", calories_per_100g=12, protein=1.5, carbs=1.3, fat=0.2, category="Овощи"),
            Product(name="Шпинат", calories_per_100g=22, protein=2.9, carbs=2.0, fat=0.3, category="Овощи"),
            Product(name="Кабачки", calories_per_100g=24, protein=0.6, carbs=4.6, fat=0.3, category="Овощи"),
            Product(name="Баклажаны", calories_per_100g=24, protein=1.2, carbs=4.5, fat=0.1, category="Овощи"),
            Product(name="Тыква", calories_per_100g=22, protein=1.0, carbs=4.4, fat=0.1, category="Овощи"),
            Product(name="Петрушка", calories_per_100g=47, protein=3.7, carbs=7.6, fat=0.4, category="Овощи"),
            Product(name="Укроп", calories_per_100g=40, protein=2.5, carbs=6.3, fat=0.5, category="Овощи"),
            
            # Дополнительные фрукты и ягоды
            Product(name="Мандарин", calories_per_100g=38, protein=0.8, carbs=7.5, fat=0.2, category="Фрукты"),
            Product(name="Лимон", calories_per_100g=16, protein=0.9, carbs=3.0, fat=0.1, category="Фрукты"),
            Product(name="Виноград", calories_per_100g=65, protein=0.6, carbs=15.4, fat=0.2, category="Фрукты"),
            Product(name="Вишня", calories_per_100g=52, protein=1.1, carbs=11.3, fat=0.2, category="Фрукты"),
            Product(name="Черешня", calories_per_100g=50, protein=1.1, carbs=10.6, fat=0.4, category="Фрукты"),
            Product(name="Слива", calories_per_100g=42, protein=0.8, carbs=9.6, fat=0.3, category="Фрукты"),
            Product(name="Персик", calories_per_100g=46, protein=0.9, carbs=11.1, fat=0.1, category="Фрукты"),
            Product(name="Абрикос", calories_per_100g=44, protein=0.9, carbs=9.0, fat=0.1, category="Фрукты"),
            Product(name="Киви", calories_per_100g=47, protein=1.0, carbs=10.3, fat=0.5, category="Фрукты"),
            Product(name="Ананас", calories_per_100g=52, protein=0.4, carbs=11.8, fat=0.1, category="Фрукты"),
            Product(name="Манго", calories_per_100g=67, protein=0.6, carbs=15.0, fat=0.4, category="Фрукты"),
            Product(name="Смородина черная", calories_per_100g=44, protein=1.0, carbs=7.3, fat=0.4, category="Ягоды"),
            Product(name="Смородина красная", calories_per_100g=43, protein=0.6, carbs=7.7, fat=0.2, category="Ягоды"),
            Product(name="Крыжовник", calories_per_100g=45, protein=0.7, carbs=9.1, fat=0.2, category="Ягоды"),
            Product(name="Брусника", calories_per_100g=43, protein=0.7, carbs=8.2, fat=0.5, category="Ягоды"),
            Product(name="Клюква", calories_per_100g=28, protein=0.5, carbs=6.8, fat=0.2, category="Ягоды"),
            
            # Дополнительные орехи и семечки
            Product(name="Фундук", calories_per_100g=704, protein=16.1, carbs=9.9, fat=66.9, category="Орехи и семечки"),
            Product(name="Арахис", calories_per_100g=548, protein=26.3, carbs=9.9, fat=45.2, category="Орехи и семечки"),
            Product(name="Кешью", calories_per_100g=553, protein=25.7, carbs=13.2, fat=42.2, category="Орехи и семечки"),
            Product(name="Фисташки", calories_per_100g=556, protein=20.0, carbs=7.0, fat=50.0, category="Орехи и семечки"),
            Product(name="Семечки подсолнуха", calories_per_100g=601, protein=20.7, carbs=10.5, fat=52.9, category="Орехи и семечки"),
            Product(name="Семечки тыквы", calories_per_100g=559, protein=24.5, carbs=4.7, fat=49.1, category="Орехи и семечки"),
            
            # Дополнительные молочные продукты
            Product(name="Молоко 1.5%", calories_per_100g=44, protein=2.8, carbs=4.7, fat=1.5, category="Молочные продукты"),
            Product(name="Кефир 1%", calories_per_100g=40, protein=2.8, carbs=4.0, fat=1.0, category="Молочные продукты"),
            Product(name="Сметана 15%", calories_per_100g=158, protein=2.6, carbs=3.0, fat=15.0, category="Молочные продукты"),
            Product(name="Сыр голландский", calories_per_100g=377, protein=26.0, carbs=0.0, fat=31.0, category="Молочные продукты"),
            Product(name="Брынза", calories_per_100g=260, protein=17.9, carbs=0.0, fat=20.1, category="Молочные продукты"),
            Product(name="Простокваша", calories_per_100g=53, protein=2.9, carbs=4.1, fat=2.5, category="Молочные продукты"),
            
            # Дополнительные крупы и злаки
            Product(name="Рис бурый", calories_per_100g=337, protein=6.3, carbs=65.1, fat=4.4, category="Крупы"),
            Product(name="Перловка", calories_per_100g=315, protein=9.3, carbs=73.7, fat=1.1, category="Крупы"),
            Product(name="Манка", calories_per_100g=328, protein=10.3, carbs=70.6, fat=1.0, category="Крупы"),
            Product(name="Кукурузная крупа", calories_per_100g=328, protein=8.3, carbs=71.0, fat=1.2, category="Крупы"),
            Product(name="Булгур", calories_per_100g=342, protein=12.3, carbs=57.6, fat=1.3, category="Крупы"),
            
            # Дополнительные масла
            Product(name="Масло подсолнечное", calories_per_100g=899, protein=0.0, carbs=0.0, fat=99.9, category="Масла и жиры"),
            Product(name="Маргарин", calories_per_100g=743, protein=0.5, carbs=1.0, fat=82.0, category="Масла и жиры"),
            
            # Дополнительные бобовые
            Product(name="Фасоль белая", calories_per_100g=102, protein=7.0, carbs=16.9, fat=0.5, category="Бобовые"),
            Product(name="Фасоль красная", calories_per_100g=93, protein=8.4, carbs=13.7, fat=0.3, category="Бобовые"),
            Product(name="Горох", calories_per_100g=298, protein=20.5, carbs=53.3, fat=2.0, category="Бобовые"),
            Product(name="Нут", calories_per_100g=364, protein=19.3, carbs=61.0, fat=6.0, category="Бобовые"),
            
            # Дополнительные напитки
            Product(name="Чай черный", calories_per_100g=1, protein=0.0, carbs=0.3, fat=0.0, category="Напитки"),
            Product(name="Сок апельсиновый", calories_per_100g=36, protein=0.7, carbs=8.1, fat=0.2, category="Напитки"),
            Product(name="Сок яблочный", calories_per_100g=46, protein=0.1, carbs=11.3, fat=0.1, category="Напитки"),
            Product(name="Компот", calories_per_100g=60, protein=0.2, carbs=15.0, fat=0.1, category="Напитки"),
            
            # Дополнительные сладости
            Product(name="Сахар", calories_per_100g=387, protein=0.0, carbs=99.7, fat=0.0, category="Сладости"),
            Product(name="Шоколад молочный", calories_per_100g=534, protein=7.6, carbs=60.2, fat=29.7, category="Сладости"),
            Product(name="Печенье овсяное", calories_per_100g=437, protein=6.5, carbs=71.4, fat=14.1, category="Сладости"),
            Product(name="Зефир", calories_per_100g=304, protein=0.8, carbs=79.8, fat=0.0, category="Сладости"),
        ]
        
        # Добавляем мега-продукты
        for product in mega_products:
            db.session.add(product)
        
        db.session.commit()
        
        new_count = Product.query.count()
        added_count = len(mega_products)
        
        flash(f'🎉 МЕГА успех! Добавлено {added_count} продуктов! Общее количество: {new_count}', 'success')
        logging.info(f"Added {added_count} mega products, total: {new_count}")
        
        return redirect(url_for('products'))
        
    except Exception as e:
        logging.error(f"Error loading mega products: {str(e)}")
        flash(f'Ошибка при добавлении мега-продуктов: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/product_count')
def product_count():
    """Показывает текущее количество продуктов в базе"""
    try:
        count = Product.query.count()
        # Получаем категории с количеством
        from sqlalchemy import text
        category_result = db.session.execute(text("""
            SELECT category, COUNT(*) as count 
            FROM products 
            GROUP BY category 
            ORDER BY category
        """))
        category_info = {row[0]: row[1] for row in category_result}
        
        return jsonify({
            'total_products': count,
            'categories': category_info,
            'message': f'В базе данных {count} продуктов в {len(category_info)} категориях'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reload_products')
def reload_products():
    """Принудительная перезагрузка всех продуктов"""
    try:
        auto_load_all_products()
        flash('Продукты успешно перезагружены!', 'success')
        return redirect(url_for('products'))
    except Exception as e:
        flash(f'Ошибка при перезагрузке продуктов: {str(e)}', 'error')
        return redirect(url_for('products'))
def check_schema():
    """Check database schema status"""
    try:
        from sqlalchemy import text
        schema_status = {}
        
        # Check if users table exists
        users_table_check = db.session.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')"
        ))
        schema_status['users_table_exists'] = users_table_check.scalar()
        
        # Check if food_entries table exists
        food_entries_table_check = db.session.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'food_entries')"
        ))
        food_entries_table_exists = food_entries_table_check.scalar()
        schema_status['food_entries_table_exists'] = food_entries_table_exists
        
        if food_entries_table_exists:
            # Check if user_id column exists in food_entries
            food_entries_user_id_check = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='food_entries' AND column_name='user_id'"
            ))
            schema_status['food_entries_user_id_exists'] = food_entries_user_id_check.fetchone() is not None
            
            # Check record count in food_entries
            food_entries_count = db.session.execute(text("SELECT COUNT(*) FROM food_entries")).scalar() or 0
            schema_status['food_entries_count'] = food_entries_count
        else:
            schema_status['food_entries_user_id_exists'] = False
            schema_status['food_entries_count'] = 0
        
        # Check if user_profile table exists
        user_profile_table_check = db.session.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_profile')"
        ))
        user_profile_table_exists = user_profile_table_check.scalar()
        schema_status['user_profile_table_exists'] = user_profile_table_exists
        
        if user_profile_table_exists:
            # Check if user_id column exists in user_profile
            user_profile_user_id_check = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='user_profile' AND column_name='user_id'"
            ))
            schema_status['user_profile_user_id_exists'] = user_profile_user_id_check.fetchone() is not None
            
            # Check record count in user_profile
            user_profile_count = db.session.execute(text("SELECT COUNT(*) FROM user_profile")).scalar() or 0
            schema_status['user_profile_count'] = user_profile_count
        else:
            schema_status['user_profile_user_id_exists'] = False
            schema_status['user_profile_count'] = 0
        
        # Determine overall status
        issues = []
        
        if not schema_status['food_entries_table_exists']:
            issues.append('food_entries table missing')
        elif not schema_status['food_entries_user_id_exists']:
            issues.append('user_id column missing in food_entries table')
        
        if not schema_status['user_profile_table_exists']:
            issues.append('user_profile table missing')
        elif not schema_status['user_profile_user_id_exists']:
            issues.append('user_id column missing in user_profile table')
        
        if issues:
            return jsonify({
                'status': 'error',
                'message': f'Schema issues found: {", ".join(issues)}',
                'action': 'Run migration',
                'details': schema_status
            })
        
        return jsonify({
            'status': 'ok',
            'message': f'Schema is correct. Found {schema_status["food_entries_count"]} food entries and {schema_status["user_profile_count"]} user profiles.',
            'details': schema_status
        })
        
    except Exception as e:
        logging.error(f"Schema check failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Schema check failed: {str(e)}'
        }), 500

@app.route('/migrate_all')
def migrate_all_route():
    """Comprehensive migration endpoint for all tables"""
    try:
        logging.info("Comprehensive migration requested")
        
        # Run all migrations
        results = {
            'schema_check': check_and_migrate_schema(),
            'food_entries': False,
            'user_profile': False
        }
        
        messages = []
        
        if results['schema_check']:
            messages.append('Общая миграция схемы выполнена успешно')
        
        success_count = sum(1 for result in results.values() if result)
        
        if success_count > 0:
            flash(f'Миграция завершена! Выполнено {success_count} операций. {" | ".join(messages)}', 'success')
        else:
            flash('Миграция не требуется - все таблицы уже в порядке!', 'info')
        
        return redirect(url_for('index'))
        
    except Exception as e:
        logging.error(f"Comprehensive migration failed: {str(e)}")
        flash(f'Ошибка комплексной миграции: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/migrate_food_entries')
def migrate_food_entries_route():
    """Manual migration endpoint for food_entries table"""
    try:
        logging.info("Manual food_entries migration requested")
        result = migrate_food_entries_table()
        
        if result:
            flash('Миграция food_entries успешно выполнена!', 'success')
        else:
            flash('Миграция не требуется - таблица food_entries уже в порядке!', 'info')
        
        return redirect(url_for('index'))
        
    except Exception as e:
        logging.error(f"Manual food_entries migration failed: {str(e)}")
        flash(f'Ошибка миграции food_entries: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/fix_profile_schema')
def fix_profile_schema():
    """Manual endpoint to fix profile-related database schema issues"""
    try:
        logging.info("Manual schema fix for profile requested")
        
        # Check and create tables if needed
        with app.app_context():
            db.create_all()
            
            # Run comprehensive migration
            check_and_migrate_schema()
            
            # Verify UserProfile table structure
            from sqlalchemy import text
            user_profile_columns = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='user_profile'"
            )).fetchall()
            
            column_names = [col[0] for col in user_profile_columns]
            logging.info(f"UserProfile table columns: {column_names}")
            
            if 'user_id' not in column_names:
                flash('Column user_id is missing from user_profile table. Running specific migration...', 'warning')
                migrate_user_profile_table()
            
        flash('Схема базы данных для профиля исправлена! Попробуйте зайти в профиль снова.', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        logging.error(f"Profile schema fix failed: {str(e)}")
        flash(f'Ошибка исправления схемы профиля: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/migrate_user_profile')
def migrate_user_profile_route():
    """Manual migration endpoint for user_profile table"""
    try:
        logging.info("Manual user_profile migration requested")
        result = migrate_user_profile_table()
        
        if result:
            flash('Миграция user_profile успешно выполнена!', 'success')
        else:
            flash('Миграция не требуется - таблица уже в порядке!', 'info')
        
        return redirect(url_for('profile'))
        
    except Exception as e:
        logging.error(f"Manual migration failed: {str(e)}")
        flash(f'Ошибка миграции: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/init_db')
def initialize_database():
    """Принудительная инициализация базы данных"""
    try:
        logging.info("Manual database initialization requested")
        init_database()
        flash('База данных успешно инициализирована!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Manual database initialization failed: {str(e)}")
        flash(f'Ошибка инициализации базы данных: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/cleanup_duplicates')
def cleanup_duplicates():
    """Оптимизированная очистка дубликатов (избегаем timeout)"""
    try:
        logging.info("Начинаем оптимизированную очистку дубликатов...")
        
        db.session.expire_all()
        from sqlalchemy import text
        
        # Шаг 1: Обновляем food_entries пакетно
        logging.info("Обновляем food_entries...")
        update_result = db.session.execute(text("""
            UPDATE food_entries 
            SET product_id = (
                SELECT MIN(p2.id) 
                FROM products p2 
                WHERE p2.name = (SELECT name FROM products p3 WHERE p3.id = food_entries.product_id)
            )
            WHERE product_id IN (
                SELECT p.id
                FROM products p
                JOIN (
                    SELECT name, MIN(id) as min_id
                    FROM products
                    GROUP BY name
                    HAVING COUNT(id) > 1
                ) dups ON p.name = dups.name AND p.id != dups.min_id
            )
        """))
        
        # Handle rowcount access for SQLAlchemy 2.x compatibility
        updated_entries = getattr(update_result, 'rowcount', 0)
        logging.info(f"Обновлено {updated_entries} food_entries")
        
        # Шаг 2: Удаляем дубликаты одним запросом
        logging.info("Удаляем дубликаты...")
        delete_result = db.session.execute(text("""
            DELETE FROM products 
            WHERE id IN (
                SELECT p.id
                FROM (
                    SELECT p.id, p.name,
                           ROW_NUMBER() OVER (PARTITION BY p.name ORDER BY p.id) as rn
                    FROM products p
                ) p
                WHERE p.name IN (
                    SELECT name
                    FROM products
                    GROUP BY name
                    HAVING COUNT(id) > 1
                )
                AND p.rn > 1
            )
        """))
        
        # Handle rowcount access for SQLAlchemy 2.x compatibility
        deleted_count = getattr(delete_result, 'rowcount', 0)
        logging.info(f"Удалено {deleted_count} дубликатов")
        
        db.session.commit()
        db.session.expire_all()
        
        flash(f'✅ Очистка завершена! Удалено {deleted_count} дубликатов, обновлено {updated_entries} записей.', 'success')
        
    except Exception as e:
        logging.error(f"Ошибка в cleanup_duplicates: {str(e)}")
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('products'))

@app.route('/api/get_duplicate_count')
def get_duplicate_count():
    """Получить количество дубликатов в базе"""
    try:
        # Принудительное обновление сессии
        db.session.expire_all()
        
        from sqlalchemy import text
        
        # Подсчитываем количество дубликатов
        result = db.session.execute(text("""
            SELECT COUNT(*) as duplicate_count
            FROM (
                SELECT name
                FROM products 
                GROUP BY name 
                HAVING COUNT(id) > 1
            ) as duplicates
        """))
        
        duplicate_groups = result.scalar() or 0
        
        # Подсчитываем общее количество лишних продуктов
        result2 = db.session.execute(text("""
            SELECT SUM(count - 1) as total_duplicates
            FROM (
                SELECT COUNT(id) as count
                FROM products 
                GROUP BY name 
                HAVING COUNT(id) > 1
            ) as duplicates
        """))
        
        total_duplicates = result2.scalar() or 0
        
        return jsonify({
            'success': True,
            'duplicate_groups': duplicate_groups,
            'total_duplicates': total_duplicates,
            'total_products': Product.query.count()
        })
        
    except Exception as e:
        logging.error(f"Ошибка получения статистики дубликатов: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/show_duplicates')
def show_duplicates():
    """Показать список дубликатов без удаления"""
    try:
        # Принудительное обновление сессии
        db.session.expire_all()
        
        from sqlalchemy import func, text
        
        # Используем прямой SQL запрос для поиска дубликатов
        duplicate_query = db.session.execute(text("""
            SELECT name, COUNT(id) as count
            FROM products 
            GROUP BY name 
            HAVING COUNT(id) > 1
            ORDER BY name
        """))
        
        duplicates = duplicate_query.fetchall()
        
        if not duplicates:
            flash('Дубликаты не найдены! База данных чистая.', 'info')
            return redirect(url_for('products'))
        
        # Получаем детальную информацию о каждом дубликате
        duplicate_details = []
        total_duplicates = 0
        
        for duplicate in duplicates:
            product_name = duplicate[0]  # name
            count = duplicate[1]        # count
            
            # Находим все продукты с одинаковым именем
            same_name_products = Product.query.filter_by(name=product_name).order_by(Product.id).all()
            
            duplicate_details.append({
                'name': product_name,
                'count': count,
                'products': same_name_products
            })
            
            total_duplicates += (int(count) - 1)  # Исключаем оригинал
        
        flash(f'Найдено {len(duplicates)} групп дубликатов. Всего дубликатов для удаления: {total_duplicates}', 'warning')
        
        # Рендерим специальную страницу для показа дубликатов
        return render_template('show_duplicates.html', duplicate_details=duplicate_details, total_duplicates=total_duplicates)
        
    except Exception as e:
        logging.error(f"Ошибка при поиске дубликатов: {str(e)}")
        flash(f'Ошибка при поиске дубликатов: {str(e)}', 'danger')
        return redirect(url_for('products'))
@app.route('/load_qwen_products')
def load_qwen_products():
    """Оптимизированная загрузка Qwen продуктов через прямой SQL"""
    try:
        from sqlalchemy import text
        
        current_count = Product.query.count()
        logging.info(f"Loading Qwen products, current count: {current_count}")
        
        # Проверяем на дубликаты
        check = db.session.execute(text("SELECT id FROM products WHERE name LIKE '%Овсянка%' LIMIT 1")).fetchone()
        if check:
            flash('📝 Qwen продукты уже загружены!', 'info')
            return redirect(url_for('products'))
        
        # Ключевые продукты с предварительно рассчитанными калориями
        products = [
            # Базовые (ключевые)
            ("Овсянка (сухая)", 379.3, 12.3, 66.0, 6.9, "Крупы"),
            ("Гречка (сухая)", 297.1, 12.6, 62.1, 3.3, "Крупы"),
            ("Куриная грудка (отварная)", 109.1, 23.0, 0.0, 1.9, "Мясо и птица"),
            ("Творог 0%", 75.0, 18.0, 3.0, 0.0, "Молочные"),
            
            # Салаты (отдельная категория)
            ("Греческий салат", 143.0, 3.0, 5.0, 12.0, "Салаты"),
            ("Цезарь с курицей", 199.0, 10.0, 6.0, 15.0, "Салаты"),
            ("Оливье (с колбасой)", 168.0, 5.0, 10.0, 12.0, "Салаты"),
            ("Винегрет", 84.0, 2.0, 12.0, 4.0, "Салаты"),
            
            # Готовые блюда
            ("Паста с томатным соусом", 197.0, 8.0, 30.0, 5.0, "Готовые блюда"),
            ("Плов (с курицей)", 212.0, 10.0, 25.0, 8.0, "Готовые блюда"),
            
            # Орехи и др.
            ("Миндаль (очищенный)", 609.0, 21.0, 22.0, 49.0, "Орехи и семечки"),
            ("Хумус", 181.0, 8.0, 13.0, 14.0, "Закуски"),
            
            # Десерты
            ("Шоколад 70% какао", 572.0, 8.0, 45.0, 40.0, "Сладости"),
            ("Тофу", 56.0, 8.0, 2.0, 4.0, "Веганские")
        ]
        
        added_count = 0
        salad_count = 0
        
        for name, calories, protein, carbs, fat, category in products:
            existing = db.session.execute(
                text("SELECT 1 FROM products WHERE name = :name LIMIT 1"),
                {'name': name}
            ).fetchone()
            
            if not existing:
                db.session.execute(text("""
                    INSERT INTO products (name, calories_per_100g, protein, carbs, fat, category, created_at)
                    VALUES (:name, :calories, :protein, :carbs, :fat, :category, NOW())
                """), {
                    'name': name, 'calories': calories, 'protein': protein,
                    'carbs': carbs, 'fat': fat, 'category': category
                })
                added_count += 1
                if category == "Салаты":
                    salad_count += 1
        
        db.session.commit()
        new_count = Product.query.count()
        
        flash(f'🎉 Добавлено {added_count} Qwen продуктов! ({salad_count} салатов). Всего: {new_count}', 'success')
        return redirect(url_for('products'))
        
    except Exception as e:
        logging.error(f"Qwen products error: {str(e)}")
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('products'))

@app.route('/migrate_categories')
def migrate_categories():
    """Миграция категорий: объединяем мясо и яйца в 'Мясо и птица'"""
    try:
        # Обновляем продукты с категорией 'Мясо и яйца'
        products_meat_eggs = Product.query.filter_by(category='Мясо и яйца').all()
        for product in products_meat_eggs:
            product.category = 'Мясо и птица'
        
        # Обновляем яйца из 'Молочные продукты'
        all_dairy_products = Product.query.filter_by(category='Молочные продукты').all()
        egg_products = [p for p in all_dairy_products if 'яйц' in p.name.lower()]
        for product in egg_products:
            product.category = 'Мясо и птица'
        
        # Обновляем продукты с категорией 'Яйца'
        egg_category_products = Product.query.filter_by(category='Яйца').all()
        for product in egg_category_products:
            product.category = 'Мясо и птица'
        
        db.session.commit()
        
        total_updated = len(products_meat_eggs) + len(egg_products) + len(egg_category_products)
        
        logging.info(f"Миграция категорий успешно завершена. Обновлено: {total_updated} продуктов")
        flash(f'Миграция успешно завершена! Обновлено {total_updated} продуктов в категории "Мясо и птица".', 'success')
        return redirect(url_for('products'))
        
    except Exception as e:
        logging.error(f"Ошибка при миграции категорий: {str(e)}")
        flash(f'Ошибка при миграции категорий: {str(e)}', 'danger')
        return redirect(url_for('products'))

@app.route('/migrate_db')
def migrate_db():
    """Добавляет столбец category в существующую таблицу products"""
    try:
        # Проверяем, есть ли уже столбец category
        from sqlalchemy import text
        result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='products' AND column_name='category'"))
        if result.fetchone():
            flash('Столбец category уже существует!', 'info')
            return redirect(url_for('products'))
        
        # Добавляем столбец category
        db.session.execute(text("ALTER TABLE products ADD COLUMN category VARCHAR(50) DEFAULT 'Прочее'"))
        db.session.commit()
        
        logging.info("Столбец category успешно добавлен в таблицу products")
        flash('База данных обновлена! Столбец category добавлен.', 'success')
        return redirect(url_for('products'))
        
    except Exception as e:
        logging.error(f"Ошибка при миграции БД: {str(e)}")
        flash(f'Ошибка при обновлении БД: {str(e)}', 'danger')
        return redirect(url_for('products'))

def create_tables():
    """Create database tables if they don't exist"""
    try:
        with app.app_context():
            db.create_all()
            logging.info("Database tables created successfully")
            
            # Add some default products if none exist
            if Product.query.count() == 0:
                default_products = [
                    Product(name="Хлеб белый", calories_per_100g=265, protein=8.1, carbs=48.8, fat=3.2, category="Хлебобулочные"),
                    Product(name="Молоко 3.2%", calories_per_100g=60, protein=2.9, carbs=4.7, fat=3.2, category="Молочные"),
                    Product(name="Яйцо куриное", calories_per_100g=155, protein=12.7, carbs=0.7, fat=10.9, category="Мясо и птица"),
                    Product(name="Рис белый", calories_per_100g=365, protein=7.5, carbs=78.9, fat=0.7, category="Крупы"),
                    Product(name="Курица грудка", calories_per_100g=165, protein=31.0, carbs=0.0, fat=3.6, category="Мясо и птица"),
                    Product(name="Яблоко", calories_per_100g=47, protein=0.4, carbs=9.8, fat=0.4, category="Фрукты"),
                    Product(name="Банан", calories_per_100g=96, protein=1.5, carbs=21.0, fat=0.2, category="Фрукты"),
                    Product(name="Картофель", calories_per_100g=80, protein=2.0, carbs=16.3, fat=0.4, category="Овощи")
                ]
                
                for product in default_products:
                    db.session.add(product)
                
                db.session.commit()
                logging.info(f"Added {len(default_products)} default products")
                
    except Exception as e:
        logging.error(f"Error creating database tables: {str(e)}")
        raise

def check_database_connection():
    """Check if database connection is working"""
    try:
        with app.app_context():
            # Try to execute a simple query
            db.session.execute(db.text('SELECT 1'))
            logging.info("Database connection successful")
            return True
    except Exception as e:
        logging.error(f"Database connection failed: {str(e)}")
        return False

@app.route('/toggle_theme')
@login_required
def toggle_theme():
    """API endpoint для переключения темы"""
    theme = request.args.get('theme', 'light')
    
    # Возвращаем JSON ответ для AJAX запроса
    return jsonify({
        'status': 'success',
        'theme': theme,
        'message': f'Тема изменена на {"темную" if theme == "dark" else "светлую"}'
    })

@app.route('/achievements')
@login_required
def achievements():
    """Страница достижений и статистики уровня"""
    current_user = get_current_user()
    if not current_user:
        flash('Ошибка аутентификации. Пожалуйста, войдите в систему снова.', 'error')
        return redirect(url_for('login'))
    
    user_level = get_or_create_user_level(current_user.id)
    achievements_list = user_level.get_achievements()
    
    # Проверяем новые достижения
    new_achievements = check_achievements(user_level)
    if new_achievements:
        db.session.commit()
        for achievement in new_achievements:
            flash(f'🏆 Новое достижение: {achievement}!', 'success')
    
    return render_template('achievements.html', 
                         user_level=user_level, 
                         achievements=achievements_list,
                         current_user=current_user)

@app.route('/api/user_level')
@login_required
def api_user_level():
    """АPI для получения информации о уровне пользователя"""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Ошибка аутентификации'})
    
    user_level = get_or_create_user_level(current_user.id)
    
    return jsonify({
        'success': True,
        'level': user_level.level,
        'experience': user_level.experience,
        'experience_to_next': user_level.experience_to_next_level,
        'progress_percentage': user_level.progress_percentage,
        'title': user_level.title,
        'total_food_entries': user_level.total_food_entries,
        'total_products_added': user_level.total_products_added,
        'days_active': user_level.days_active
    })

if __name__ == '__main__':
    # Check database connection before starting the app
    if check_database_connection():
        # Create tables if they don't exist
        create_tables()
        logging.info("Starting Flask application...")
        
        # Определяем порт для Render
        port = int(os.environ.get('PORT', 5000))
        
        # Запускаем приложение
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        logging.error("Cannot start application - database connection failed")
        print("\n" + "="*50)
        print("DATABASE CONNECTION ERROR")
        print("="*50)
        print("The application cannot connect to PostgreSQL database.")
        print("\nPossible solutions:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check database credentials in the connection string")
        print("3. Verify the database 'calckal' exists")
        print("4. For local development, ensure the connection string is:")
        print("   postgresql://postgres:1234@localhost/calckal")
        print("5. Set DATABASE_URL environment variable if different")
        print("\nCurrent DATABASE_URL:", os.environ.get('DATABASE_URL', 'not set'))
        print("="*50)