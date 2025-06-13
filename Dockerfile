FROM python:3.11-slim

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо requirements.txt
COPY requirements.txt .

# Встановлюємо Python залежності
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копіюємо код проекту
COPY . .


# Відкриваємо порт
EXPOSE 8000

# Команда за замовчуванням
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]