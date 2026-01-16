# Django Project Setup with PostgreSQL

## 📌 Prerequisites
Ensure you have the following installed:
- Python (>=3.8)
- PostgreSQL
- Git
- Virtualenv (recommended)

---

## ⚙️ Installation Steps

### 1️⃣ Clone the Repository
```sh
git clone https://github.com/YOUR_USERNAME/YOUR_PROJECT.git
cd YOUR_PROJECT
```

### 2️⃣ Create a Virtual Environment
```sh
python -m venv venv
source venv/bin/activate  # On Windows, use 'venv\Scripts\activate'
```

### 3️⃣ Install Dependencies
```sh
pip install -r requirements.txt
```

---

## 🗄️ PostgreSQL Database Setup

### 4️⃣ Create a PostgreSQL Database
1. Login to PostgreSQL:
   ```sh
   sudo -u postgres psql
   ```
2. Create a database:
   ```sql
   CREATE DATABASE your_database_name;
   ```
3. Create a user and grant permissions:
   ```sql
   CREATE USER your_username WITH PASSWORD 'your_password';
   ALTER ROLE your_username SET client_encoding TO 'utf8';
   ALTER ROLE your_username SET default_transaction_isolation TO 'read committed';
   ALTER ROLE your_username SET timezone TO 'UTC';
   GRANT ALL PRIVILEGES ON DATABASE your_database_name TO your_username;
   \q
   ```

### 5️⃣ Configure Database in Django
Edit **`settings.py`**:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_database_name',
        'USER': 'your_username',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

---

## 🔄 Final Setup

### 6️⃣ Apply Migrations
```sh
python manage.py migrate
```

### 7️⃣ Create a Superuser
```sh
python manage.py createsuperuser
```
Follow the prompts to create an admin account.

### 8️⃣ Run the Development Server
```sh
python manage.py runserver
```
Visit **http://127.0.0.1:8000/** in your browser.

---

## 🛠️ Additional Commands

### Install Additional Packages
```sh
pip install package_name
```

### Update Dependencies
```sh
pip freeze > requirements.txt
```

### Run Tests
```sh
python manage.py test
```

---

## 🎯 Next Steps
- Deploy using **Gunicorn & Nginx** (for production)
- Use **Docker** for containerization
- Implement **CI/CD Pipelines**

Happy Coding! 🚀

