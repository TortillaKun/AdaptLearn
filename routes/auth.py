from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from flask_bcrypt import Bcrypt
from seguridad import rate_limit, sanitizar_input, validar_email, validar_request_json, login_requerido

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()

def get_db():
    from app import get_db
    return get_db()

@auth_bp.route('/registro', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def registro():
    valido, error = validar_request_json()
    if not valido:
        return jsonify({'error': 'Input inválido'}), 400

    datos           = request.json or {}
    nombre_completo = sanitizar_input(datos.get('nombre', ''), max_len=100)
    email           = sanitizar_input(datos.get('email', ''), max_len=100)
    password        = datos.get('password', '')
    interes         = sanitizar_input(datos.get('interes', ''), max_len=50)

    if not nombre_completo or not email or not password:
        return jsonify({'error': 'Todos los campos son requeridos'}), 400
    if not validar_email(email):
        return jsonify({'error': 'Correo electrónico inválido'}), 400
    if len(password) < 8:
        return jsonify({'error': 'La contraseña debe tener mínimo 8 caracteres'}), 400

    partes   = nombre_completo.strip().split(' ', 1)
    nombre   = partes[0]
    apellido = partes[1] if len(partes) > 1 else ''
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    con = get_db()
    cur = con.cursor()
    try:
        cur.execute("""INSERT INTO usuarios (nombre, apellido, email, password, interes)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (nombre, apellido, email.lower(), password_hash, interes))
        con.commit()
        return jsonify({'mensaje': f'Cuenta creada para {nombre}'}), 201
    except Exception:
        return jsonify({'error': 'El correo ya está registrado'}), 400
    finally:
        cur.close()
        con.close()

@auth_bp.route('/login', methods=['POST'])
@rate_limit(max_requests=10, window=60)
def login():
    valido, _ = validar_request_json()
    if not valido:
        return jsonify({'error': 'Input inválido'}), 400

    datos    = request.json or {}
    email    = sanitizar_input(datos.get('email', ''), max_len=100)
    password = datos.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Correo y contraseña requeridos'}), 400

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, nombre, password, interes FROM usuarios WHERE email = %s", (email.lower(),))
    usuario = cur.fetchone()
    cur.close()
    con.close()

    if usuario and bcrypt.check_password_hash(usuario[2], password):
        session['usuario_id'] = usuario[0]
        session['nombre']     = usuario[1]
        session['interes']    = usuario[3]
        return jsonify({
            'mensaje':  f'Bienvenido {usuario[1]}',
            'nombre':   usuario[1],
            'interes':  usuario[3],
            'redirect': '/chat'
        }), 200
    return jsonify({'error': 'Correo o contraseña incorrectos'}), 401

@auth_bp.route('/login/google')
def login_google():
    from app import oauth
    redirect_uri = url_for('auth.auth_google', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route('/auth/google')
def auth_google():
    from app import oauth
    token     = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    if not user_info:
        return redirect(url_for('index'))

    email           = sanitizar_input(user_info.get('email', ''), max_len=100)
    nombre_completo = sanitizar_input(user_info.get('name', ''), max_len=100)
    partes          = nombre_completo.strip().split(' ', 1)
    nombre          = partes[0]
    apellido        = partes[1] if len(partes) > 1 else ''

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, nombre, interes FROM usuarios WHERE email = %s", (email.lower(),))
    usuario = cur.fetchone()

    if usuario:
        session['usuario_id'] = usuario[0]
        session['nombre']     = usuario[1]
        session['interes']    = usuario[2]
        cur.close(); con.close()
        if not usuario[2]:
            return redirect(url_for('auth.completar_perfil'))
        return redirect(url_for('chat'))
    else:
        password_dummy = bcrypt.generate_password_hash('google_auth_dummy').decode('utf-8')
        cur.execute("""INSERT INTO usuarios (nombre, apellido, email, password, interes)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (nombre, apellido, email.lower(), password_dummy, ''))
        con.commit()
        user_id = cur.lastrowid
        cur.close(); con.close()
        session['usuario_id'] = user_id
        session['nombre']     = nombre
        session['interes']    = ''
        return redirect(url_for('auth.completar_perfil'))

@auth_bp.route('/completar_perfil')
def completar_perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('index'))
    if session.get('interes'):
        return redirect(url_for('chat'))
    return render_template('completar_perfil.html')

@auth_bp.route('/guardar_interes', methods=['POST'])
@login_requerido
def guardar_interes():
    datos   = request.json or {}
    interes = sanitizar_input(datos.get('interes', ''), max_len=50)
    if not interes:
        return jsonify({'error': 'Interés requerido'}), 400

    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE usuarios SET interes = %s WHERE id = %s",
                (interes, session['usuario_id']))
    con.commit()
    cur.close(); con.close()
    session['interes'] = interes
    return jsonify({'mensaje': 'Perfil completado', 'redirect': '/chat'}), 200