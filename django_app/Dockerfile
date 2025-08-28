FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Создаем директорию для статических файлов
RUN mkdir -p /app/static

# Создаем скрипт для инициализации
RUN echo '#!/bin/bash\n\
echo "Waiting for PostgreSQL..."\n\
while ! pg_isready -h postgres -p 5432 -U friend_bot_user; do\n\
  sleep 1\n\
done\n\
echo "PostgreSQL is ready!"\n\
\n\
echo "Creating migrations..."\n\
python manage.py makemigrations\n\
\n\
echo "Running Django migrations..."\n\
python manage.py migrate --run-syncdb\n\
\n\
echo "Running app migrations..."\n\
python manage.py migrate\n\
\n\
echo "Initializing base data..."\n\
python manage.py init_data\n\
\n\
echo "Creating superuser..."\n\
python manage.py shell -c "\n\
from django.contrib.auth.models import User\n\
if not User.objects.filter(username=\"admin\").exists():\n\
    User.objects.create_superuser(\"admin\", \"alex-axe@mail.ru\", \"admin\")\n\
    print(\"Superuser admin created!\")\n\
else:\n\
    print(\"Superuser admin already exists!\")\n\
"\n\
\n\
echo "Starting Django..."\n\
python manage.py runserver 0.0.0.0:8000\n\
' > /app/start.sh && chmod +x /app/start.sh

# Запускаем Django с автоматической инициализацией
CMD ["/app/start.sh"]
