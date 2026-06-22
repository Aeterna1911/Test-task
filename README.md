# Payment API Test Task

Асинхронное REST API приложение для управления пользователями, счетами и обработки транзакций (эмуляция вебхуков от сторонних платежных систем).

**Стек технологий:** Python 3.11, FastAPI, SQLAlchemy 2.0 (asyncpg), PostgreSQL, Docker.

---

## Учетные данные по умолчанию
При запуске миграций автоматически создаются тестовые пользователи:

**Администратор:**
- **Email:** `admin@test.com`
- **Password:** `admin123`

**Тестовый пользователь:**
- **Email:** `user@test.com`
- **Password:** `user123`
- *Примечание: у пользователя автоматически создан счет с `account_id = 1` и нулевым балансом.*

---

## Инструкция по запуску

### Вариант 1: Запуск через Docker  

1. Перейдите в папку, где лежит docker-compose.yml.
2. Выполните команду для сборки:
   ```bash
   docker-compose up -d --build
   ```
   *При запуске контейнера с приложением автоматически выполнится скрипт `migrate.py`, который создаст таблицы и наполнит базу тестовыми данными.*
3. API будет доступно по адресу: http://localhost:8000
4. Swagger: http://localhost:8000/docs


### Вариант 2: Локальный запуск без Docker 

Для этого варианта вам потребуется локально запущенный сервер PostgreSQL.

1. **Настройка БД:** Создайте базу данных в PostgreSQL. По умолчанию приложение ожидает следующие параметры подключения:
   `postgresql+asyncpg://app_user:app_password@localhost:5432/app_db`

2. **Создайте и активируйте виртуальное окружение:**
   ```bash
   python -m venv venv
   venv\Scripts\activate    
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Запустите миграции**:
   ```bash
   python migrate.py
   ```

5. **Запустите сервер приложения:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

---

## Тестирование Webhook'а 

Для эмуляции входящего платежа отправьте `POST` запрос на эндпоинт `http://localhost:8000/webhook/payment`. 

Пример валидного тела запроса (подпись `signature` рассчитана для секретного ключа `gfdmhghif38yrf9ew0jkf32` по алгоритму SHA256):

```json
{
  "transaction_id": "5eae174f-7cd0-472c-bd36-35660f00132b",
  "user_id": 1,
  "account_id": 1,
  "amount": 100,
  "signature": "7b47e41efe564a062029da3367bde8844bea0fb049f894687cee5d57f2858bc8"
}
```