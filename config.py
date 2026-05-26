import os

class Config:
    MYSQL_HOST     = os.environ.get('MYSQLHOST',     'localhost')
    MYSQL_USER     = os.environ.get('MYSQLUSER',     'root')
    MYSQL_PASSWORD = os.environ.get('MYSQLPASSWORD', 'usuario0498')
    MYSQL_DB       = os.environ.get('MYSQLDATABASE', 'sistema_adaptativo')
    SECRET_KEY     = os.environ.get('SECRET_KEY',    'adaptlearn_secret_2024')
    GROQ_API_KEY   = os.environ.get('GROQ_API_KEY',  '')
    GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID',     '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')