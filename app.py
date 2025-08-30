from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import datetime as dt
import os
import logging
from typing import Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:1234@localhost/calckal')
# Исправляем URL для psycopg3
if database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Модели базы данных
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
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    weight = db.Column(db.Float, nullable=False)  # вес в граммах
    date = db.Column(db.Date, nullable=False, default=dt.date.today)
    meal_type = db.Column(db.String(20), nullable=False)  # завтрак, обед, ужин, перекус
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', backref=db.backref('entries', lazy=True))
    
    def __init__(self, product_id: int, weight: float, meal_type: str, date: Optional[dt.date] = None, **kwargs):
        super().__init__(**kwargs)
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
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))  # male/female
    weight = db.Column(db.Float)  # текущий вес
    height = db.Column(db.Float)  # рост в см
    activity_level = db.Column(db.String(20))  # sedentary, light, moderate, active, very_active
    goal = db.Column(db.String(20))  # lose, maintain, gain
    target_calories = db.Column(db.Integer)  # целевые калории в день
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, name: str, age: Optional[int] = None, gender: Optional[str] = None, 
                 weight: Optional[float] = None, height: Optional[float] = None, 
                 activity_level: Optional[str] = None, goal: Optional[str] = None, 
                 target_calories: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.age = age
        self.gender = gender
        self.weight = weight
        self.height = height
        self.activity_level = activity_level
        self.goal = goal
        self.target_calories = target_calories

# Маршруты
@app.route('/')
def index():
    today = dt.date.today()
    
    # Получаем записи за сегодня
    today_entries = FoodEntry.query.filter_by(date=today).all()
    
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
    
    # Получаем профиль пользователя
    profile = UserProfile.query.first()
    target_calories = profile.target_calories if profile and profile.target_calories else 2000
    
    return render_template('index.html', 
                         meals=meals,
                         total_calories=total_calories,
                         total_protein=total_protein,
                         total_carbs=total_carbs,
                         total_fat=total_fat,
                         target_calories=target_calories,
                         today=today)

@app.route('/products')
def products():
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
    
    return render_template('products.html', products=products, search=search, category=category)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        calories = float(request.form['calories'])
        protein = float(request.form.get('protein', 0))
        carbs = float(request.form.get('carbs', 0))
        fat = float(request.form.get('fat', 0))
        category = request.form.get('category', 'Прочее')
        
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
        
        flash('Продукт успешно добавлен!', 'success')
        return redirect(url_for('products'))
    
    return render_template('add_product.html')

@app.route('/add_food', methods=['GET', 'POST'])
def add_food():
    if request.method == 'POST':
        meal_type = request.form['meal_type']
        entry_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        
        added_count = 0
        
        # Обрабатываем множественные продукты
        product_ids = request.form.getlist('product_id[]')
        weights = request.form.getlist('weight[]')
        
        for i, product_id in enumerate(product_ids):
            if product_id and i < len(weights) and weights[i]:
                try:
                    food_entry = FoodEntry(
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
            flash(f'Добавлено {added_count} продуктов в дневник!', 'success')
        else:
            flash('Не удалось добавить продукты. Проверьте данные.', 'danger')
        
        return redirect(url_for('index'))
    
    products = Product.query.order_by(Product.category, Product.name).all()
    selected_product_id = request.args.get('product', type=int)
    return render_template('add_food.html', products=products, today=dt.date.today(), selected_product_id=selected_product_id)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_profile = UserProfile.query.first()
    
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
    
    return render_template('profile.html', profile=user_profile)

@app.route('/statistics')
def statistics():
    # Статистика за последние 7 дней
    from datetime import timedelta
    
    end_date = dt.date.today()
    start_date = end_date - timedelta(days=6)
    
    daily_stats = []
    current_date = start_date
    
    while current_date <= end_date:
        entries = FoodEntry.query.filter_by(date=current_date).all()
        total_calories = sum(entry.total_calories for entry in entries)
        
        daily_stats.append({
            'date': current_date.strftime('%d.%m'),
            'calories': round(total_calories, 0)
        })
        
        current_date += timedelta(days=1)
    
    # Средние значения за неделю
    week_entries = FoodEntry.query.filter(FoodEntry.date.between(start_date, end_date)).all()  # type: ignore
    
    if week_entries:
        avg_calories = sum(entry.total_calories for entry in week_entries) / 7
        avg_protein = sum(entry.total_protein for entry in week_entries) / 7
        avg_carbs = sum(entry.total_carbs for entry in week_entries) / 7
        avg_fat = sum(entry.total_fat for entry in week_entries) / 7
    else:
        avg_calories = avg_protein = avg_carbs = avg_fat = 0
    
    return render_template('statistics.html', 
                         daily_stats=daily_stats,
                         avg_calories=round(avg_calories, 0),
                         avg_protein=round(avg_protein, 1),
                         avg_carbs=round(avg_carbs, 1),
                         avg_fat=round(avg_fat, 1))

@app.route('/delete_entry/<int:entry_id>')
def delete_entry(entry_id):
    entry = FoodEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash('Запись удалена!', 'success')
    return redirect(url_for('index'))

@app.route('/api/search_products')
def search_products():
    query = request.args.get('q', '')
    products = Product.query.filter(Product.name.ilike(f'%{query}%')).limit(10).all()  # type: ignore
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'calories': product.calories_per_100g
        })
    
    return jsonify(results)

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
        ('Яйцо куриное', 155, 12.7, 0.7, 10.9, 'Молочные продукты'),
        ('Белок яичный', 44, 11.1, 0, 0, 'Молочные продукты'),
        ('Желток яичный', 352, 16.2, 1.0, 31.2, 'Молочные продукты'),
        
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
def quick_add_food():
    """API endpoint для быстрого добавления продуктов"""
    try:
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
            product_id=product.id,
            weight=weight,
            meal_type=meal_type,
            date=datetime.strptime(date_str, '%Y-%m-%d').date()
        )
        
        db.session.add(food_entry)
        db.session.commit()
        
        logging.info(f"Быстро добавлен продукт: {product_name} ({weight}г) в {meal_type}")
        
        return jsonify({
            'success': True, 
            'message': f'Добавлено: {product_name} ({weight}г) в {meal_type}'
        })
        
    except Exception as e:
        logging.error(f"Ошибка при быстром добавлении продукта: {str(e)}")
        return jsonify({'success': False, 'message': 'Произошла ошибка при добавлении'})

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

@app.before_first_request
def create_tables():
    try:
        db.create_all()
        logging.info("Таблицы БД созданы/проверены")
    except Exception as e:
        logging.error(f"Ошибка создания таблиц: {e}")

if __name__ == '__main__':
    with app.app_context():
        logging.info("Запуск приложения...")
        try:
            db.create_all()
            logging.info("Таблицы БД созданы/проверены")
            
            # Проверяем количество продуктов в БД
            current_products_count = Product.query.count()
            logging.info(f"Текущее количество продуктов в БД: {current_products_count}")
            
            # Инициализация завершена
            logging.info("Инициализация БД завершена")
        except Exception as e:
            logging.error(f"Ошибка инициализации БД: {e}")
    
    logging.info("Запускаем Flask сервер...")
    app.run(debug=True)