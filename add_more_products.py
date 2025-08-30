# Скрипт для добавления дополнительных продуктов в базу данных
from app import app, db, Product

def add_more_products():
    """Добавляет дополнительные продукты в базу данных"""
    
    with app.app_context():
        # Проверяем сколько продуктов уже есть
        current_count = Product.query.count()
        print(f"Текущее количество продуктов: {current_count}")
        
        # Дополнительные продукты
        additional_products = [
            # Рыба и морепродукты
            Product(name="Судак", calories_per_100g=84, protein=19.0, carbs=0.0, fat=0.8, category="Рыба и морепродукты"),
            Product(name="Треска", calories_per_100g=78, protein=17.5, carbs=0.0, fat=0.6, category="Рыба и морепродукты"),
            Product(name="Лосось", calories_per_100g=153, protein=20.0, carbs=0.0, fat=8.1, category="Рыба и морепродукты"),
            Product(name="Семга", calories_per_100g=219, protein=20.8, carbs=0.0, fat=15.1, category="Рыба и морепродукты"),
            Product(name="Тунец", calories_per_100g=96, protein=23.0, carbs=0.0, fat=1.0, category="Рыба и морепродукты"),
            Product(name="Сельдь", calories_per_100g=246, protein=17.7, carbs=0.0, fat=19.5, category="Рыба и морепродукты"),
            Product(name="Скумбрия", calories_per_100g=191, protein=18.0, carbs=0.0, fat=13.2, category="Рыба и морепродукты"),
            Product(name="Горбуша", calories_per_100g=147, protein=21.0, carbs=0.0, fat=7.0, category="Рыба и морепродукты"),
            Product(name="Камбала", calories_per_100g=83, protein=16.1, carbs=0.0, fat=2.6, category="Рыба и морепродукты"),
            Product(name="Щука", calories_per_100g=84, protein=18.8, carbs=0.0, fat=1.1, category="Рыба и морепродукты"),
            Product(name="Креветки", calories_per_100g=95, protein=18.9, carbs=0.8, fat=2.2, category="Рыба и морепродукты"),
            Product(name="Кальмары", calories_per_100g=74, protein=18.0, carbs=0.3, fat=0.3, category="Рыба и морепродукты"),
            Product(name="Мидии", calories_per_100g=77, protein=11.5, carbs=3.3, fat=2.0, category="Рыба и морепродукты"),
            Product(name="Краб", calories_per_100g=85, protein=16.0, carbs=0.0, fat=3.6, category="Рыба и морепродукты"),

            # Яйца
            Product(name="Яйцо перепелиное", calories_per_100g=168, protein=11.9, carbs=0.6, fat=13.1, category="Яйца"),
            Product(name="Белок яичный", calories_per_100g=44, protein=11.1, carbs=0.0, fat=0.0, category="Яйца"),
            Product(name="Желток яичный", calories_per_100g=352, protein=16.2, carbs=1.0, fat=31.2, category="Яйца"),

            # Крупы и каши
            Product(name="Рис бурый", calories_per_100g=337, protein=6.3, carbs=65.1, fat=4.4, category="Крупы"),
            Product(name="Гречка", calories_per_100g=308, protein=12.6, carbs=57.1, fat=3.3, category="Крупы"),
            Product(name="Овсянка", calories_per_100g=342, protein=12.3, carbs=59.5, fat=6.1, category="Крупы"),
            Product(name="Пшено", calories_per_100g=348, protein=11.5, carbs=69.3, fat=3.3, category="Крупы"),
            Product(name="Перловка", calories_per_100g=315, protein=9.3, carbs=73.7, fat=1.1, category="Крупы"),
            Product(name="Манка", calories_per_100g=328, protein=10.3, carbs=70.6, fat=1.0, category="Крупы"),
            Product(name="Кукурузная крупа", calories_per_100g=328, protein=8.3, carbs=71.0, fat=1.2, category="Крупы"),
            Product(name="Киноа", calories_per_100g=368, protein=14.1, carbs=57.2, fat=6.1, category="Крупы"),
            Product(name="Булгур", calories_per_100g=342, protein=12.3, carbs=57.6, fat=1.3, category="Крупы"),

            # Макаронные изделия
            Product(name="Макароны", calories_per_100g=337, protein=10.4, carbs=71.5, fat=1.1, category="Макаронные изделия"),
            Product(name="Спагетти", calories_per_100g=344, protein=10.9, carbs=71.2, fat=1.4, category="Макаронные изделия"),
            Product(name="Лапша", calories_per_100g=322, protein=10.4, carbs=70.5, fat=1.1, category="Макаронные изделия"),
            Product(name="Лазанья листы", calories_per_100g=348, protein=13.0, carbs=70.2, fat=1.4, category="Макаронные изделия"),

            # Бобовые
            Product(name="Фасоль белая", calories_per_100g=102, protein=7.0, carbs=16.9, fat=0.5, category="Бобовые"),
            Product(name="Фасоль красная", calories_per_100g=93, protein=8.4, carbs=13.7, fat=0.3, category="Бобовые"),
            Product(name="Горох", calories_per_100g=298, protein=20.5, carbs=53.3, fat=2.0, category="Бобовые"),
            Product(name="Чечевица", calories_per_100g=116, protein=9.0, carbs=16.9, fat=0.4, category="Бобовые"),
            Product(name="Нут", calories_per_100g=364, protein=19.3, carbs=61.0, fat=6.0, category="Бобовые"),
            Product(name="Соя", calories_per_100g=381, protein=34.9, carbs=17.3, fat=17.8, category="Бобовые"),

            # Овощи
            Product(name="Морковь", calories_per_100g=35, protein=1.3, carbs=6.9, fat=0.1, category="Овощи"),
            Product(name="Капуста белокочанная", calories_per_100g=27, protein=1.8, carbs=4.7, fat=0.1, category="Овощи"),
            Product(name="Капуста цветная", calories_per_100g=30, protein=2.5, carbs=4.2, fat=0.3, category="Овощи"),
            Product(name="Брокколи", calories_per_100g=28, protein=3.0, carbs=4.0, fat=0.4, category="Овощи"),
            Product(name="Огурцы", calories_per_100g=15, protein=0.8, carbs=2.5, fat=0.1, category="Овощи"),
            Product(name="Помидоры", calories_per_100g=20, protein=1.1, carbs=3.7, fat=0.2, category="Овощи"),
            Product(name="Перец болгарский", calories_per_100g=27, protein=1.3, carbs=5.3, fat=0.1, category="Овощи"),
            Product(name="Лук репчатый", calories_per_100g=47, protein=1.4, carbs=10.4, fat=0.0, category="Овощи"),
            Product(name="Чеснок", calories_per_100g=143, protein=6.5, carbs=29.9, fat=0.5, category="Овощи"),
            Product(name="Свекла", calories_per_100g=40, protein=1.5, carbs=8.8, fat=0.1, category="Овощи"),
            Product(name="Редис", calories_per_100g=19, protein=1.2, carbs=3.4, fat=0.1, category="Овощи"),
            Product(name="Салат листовой", calories_per_100g=12, protein=1.5, carbs=1.3, fat=0.2, category="Овощи"),
            Product(name="Шпинат", calories_per_100g=22, protein=2.9, carbs=2.0, fat=0.3, category="Овощи"),
            Product(name="Кабачки", calories_per_100g=24, protein=0.6, carbs=4.6, fat=0.3, category="Овощи"),
            Product(name="Баклажаны", calories_per_100g=24, protein=1.2, carbs=4.5, fat=0.1, category="Овощи"),
            Product(name="Тыква", calories_per_100g=22, protein=1.0, carbs=4.4, fat=0.1, category="Овощи"),

            # Фрукты
            Product(name="Апельсин", calories_per_100g=36, protein=0.9, carbs=8.1, fat=0.2, category="Фрукты"),
            Product(name="Мандарин", calories_per_100g=38, protein=0.8, carbs=7.5, fat=0.2, category="Фрукты"),
            Product(name="Лимон", calories_per_100g=16, protein=0.9, carbs=3.0, fat=0.1, category="Фрукты"),
            Product(name="Груша", calories_per_100g=42, protein=0.4, carbs=10.9, fat=0.3, category="Фрукты"),
            Product(name="Виноград", calories_per_100g=65, protein=0.6, carbs=15.4, fat=0.2, category="Фрукты"),
            Product(name="Клубника", calories_per_100g=41, protein=0.8, carbs=7.7, fat=0.4, category="Фрукты"),
            Product(name="Вишня", calories_per_100g=52, protein=1.1, carbs=11.3, fat=0.2, category="Фрукты"),
            Product(name="Черешня", calories_per_100g=50, protein=1.1, carbs=10.6, fat=0.4, category="Фрукты"),
            Product(name="Слива", calories_per_100g=42, protein=0.8, carbs=9.6, fat=0.3, category="Фрукты"),
            Product(name="Персик", calories_per_100g=46, protein=0.9, carbs=11.1, fat=0.1, category="Фрукты"),
            Product(name="Абрикос", calories_per_100g=44, protein=0.9, carbs=9.0, fat=0.1, category="Фрукты"),
            Product(name="Киви", calories_per_100g=47, protein=1.0, carbs=10.3, fat=0.5, category="Фрукты"),
            Product(name="Ананас", calories_per_100g=52, protein=0.4, carbs=11.8, fat=0.1, category="Фрукты"),
            Product(name="Манго", calories_per_100g=67, protein=0.6, carbs=15.0, fat=0.4, category="Фрукты"),
            Product(name="Авокадо", calories_per_100g=208, protein=2.0, carbs=7.4, fat=19.5, category="Фрукты"),

            # Ягоды
            Product(name="Малина", calories_per_100g=46, protein=0.8, carbs=8.3, fat=0.7, category="Ягоды"),
            Product(name="Черника", calories_per_100g=44, protein=1.1, carbs=7.6, fat=0.6, category="Ягоды"),
            Product(name="Смородина черная", calories_per_100g=44, protein=1.0, carbs=7.3, fat=0.4, category="Ягоды"),
            Product(name="Смородина красная", calories_per_100g=43, protein=0.6, carbs=7.7, fat=0.2, category="Ягоды"),
            Product(name="Крыжовник", calories_per_100g=45, protein=0.7, carbs=9.1, fat=0.2, category="Ягоды"),
            Product(name="Брусника", calories_per_100g=43, protein=0.7, carbs=8.2, fat=0.5, category="Ягоды"),
            Product(name="Клюква", calories_per_100g=28, protein=0.5, carbs=6.8, fat=0.2, category="Ягоды"),

            # Орехи и семечки
            Product(name="Грецкие орехи", calories_per_100g=656, protein=13.8, carbs=10.2, fat=60.8, category="Орехи и семечки"),
            Product(name="Миндаль", calories_per_100g=645, protein=18.6, carbs=16.2, fat=53.7, category="Орехи и семечки"),
            Product(name="Фундук", calories_per_100g=704, protein=16.1, carbs=9.9, fat=66.9, category="Орехи и семечки"),
            Product(name="Арахис", calories_per_100g=548, protein=26.3, carbs=9.9, fat=45.2, category="Орехи и семечки"),
            Product(name="Кешью", calories_per_100g=553, protein=25.7, carbs=13.2, fat=42.2, category="Орехи и семечки"),
            Product(name="Фисташки", calories_per_100g=556, protein=20.0, carbs=7.0, fat=50.0, category="Орехи и семечки"),
            Product(name="Семечки подсолнуха", calories_per_100g=601, protein=20.7, carbs=10.5, fat=52.9, category="Орехи и семечки"),
            Product(name="Семечки тыквы", calories_per_100g=559, protein=24.5, carbs=4.7, fat=49.1, category="Орехи и семечки"),

            # Масла и жиры
            Product(name="Масло подсолнечное", calories_per_100g=899, protein=0.0, carbs=0.0, fat=99.9, category="Масла и жиры"),
            Product(name="Масло оливковое", calories_per_100g=898, protein=0.0, carbs=0.0, fat=99.8, category="Масла и жиры"),
            Product(name="Масло сливочное", calories_per_100g=748, protein=0.5, carbs=0.8, fat=82.5, category="Масла и жиры"),
            Product(name="Маргарин", calories_per_100g=743, protein=0.5, carbs=1.0, fat=82.0, category="Масла и жиры"),
            Product(name="Сало", calories_per_100g=797, protein=1.4, carbs=0.0, fat=89.0, category="Масла и жиры"),

            # Сладости и кондитерские изделия
            Product(name="Сахар", calories_per_100g=387, protein=0.0, carbs=99.7, fat=0.0, category="Сладости"),
            Product(name="Мед", calories_per_100g=329, protein=0.8, carbs=80.3, fat=0.0, category="Сладости"),
            Product(name="Шоколад темный", calories_per_100g=546, protein=6.2, carbs=52.6, fat=35.4, category="Сладости"),
            Product(name="Шоколад молочный", calories_per_100g=534, protein=7.6, carbs=60.2, fat=29.7, category="Сладости"),
            Product(name="Печенье овсяное", calories_per_100g=437, protein=6.5, carbs=71.4, fat=14.1, category="Сладости"),
            Product(name="Вафли", calories_per_100g=425, protein=8.2, carbs=65.1, fat=14.6, category="Сладости"),
            Product(name="Мармелад", calories_per_100g=321, protein=0.1, carbs=77.7, fat=0.1, category="Сладости"),
            Product(name="Зефир", calories_per_100g=304, protein=0.8, carbs=79.8, fat=0.0, category="Сладости"),

            # Напитки
            Product(name="Чай черный", calories_per_100g=1, protein=0.0, carbs=0.3, fat=0.0, category="Напитки"),
            Product(name="Кофе", calories_per_100g=2, protein=0.2, carbs=0.3, fat=0.0, category="Напитки"),
            Product(name="Сок апельсиновый", calories_per_100g=36, protein=0.7, carbs=8.1, fat=0.2, category="Напитки"),
            Product(name="Сок яблочный", calories_per_100g=46, protein=0.1, carbs=11.3, fat=0.1, category="Напитки"),
            Product(name="Компот", calories_per_100g=60, protein=0.2, carbs=15.0, fat=0.1, category="Напитки"),
            Product(name="Минеральная вода", calories_per_100g=0, protein=0.0, carbs=0.0, fat=0.0, category="Напитки"),
        ]

        # Добавляем продукты в базу
        for product in additional_products:
            db.session.add(product)
        
        db.session.commit()
        
        new_count = Product.query.count()
        added_count = new_count - current_count
        print(f"Добавлено продуктов: {added_count}")
        print(f"Общее количество продуктов: {new_count}")

if __name__ == "__main__":
    add_more_products()