from flask import Flask, render_template, session, redirect, url_for
from flask_mysqldb import MySQL
from authlib.integrations.flask_client import OAuth
from config import Config
from seguridad import aplicar_seguridad

app = Flask(__name__)
app.config.from_object(Config)

mysql = MySQL(app)
oauth = OAuth(app)

oauth.register(
    name='google',
    client_id=app.config.get('GOOGLE_CLIENT_ID'),
    client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# ── APLICAR SEGURIDAD ──────────────────────────────
aplicar_seguridad(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/acceder')
def acceder():
    return render_template('login_registro_adaptlearn.html')

@app.route('/chat')
def chat():
    if 'usuario_id' not in session:
        return redirect(url_for('acceder'))
    return render_template('chat.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('acceder'))
    return render_template('deshboard.html')

from routes.auth import auth_bp
from routes.ejercicios import ejercicios_bp
from routes.chat import chat_bp

app.register_blueprint(auth_bp)
app.register_blueprint(ejercicios_bp)
app.register_blueprint(chat_bp)

if __name__ == '__main__':
    app.run(debug=True)