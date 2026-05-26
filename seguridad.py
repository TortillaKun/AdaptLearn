# ── AdaptLearn Security Module ─────────────────────
# Incluir en app.py: from seguridad import aplicar_seguridad
# Luego llamar: aplicar_seguridad(app)

from flask import request, jsonify, session
from functools import wraps
import re
import time
from collections import defaultdict

# ── RATE LIMITING ──────────────────────────────────
request_counts = defaultdict(list)

def rate_limit(max_requests=30, window=60):
    """Limita peticiones por IP: max_requests por window segundos"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            # Limpiar requests viejos
            request_counts[ip] = [t for t in request_counts[ip] if now - t < window]
            if len(request_counts[ip]) >= max_requests:
                return jsonify({'error': 'Demasiadas peticiones. Espera un momento.'}), 429
            request_counts[ip].append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ── SQL INJECTION PREVENTION ───────────────────────
SQL_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
    r"(--|;|/\*|\*/|xp_|0x[0-9a-fA-F]+)",
    r"(\bOR\b\s+[\w'\"]+\s*=\s*[\w'\"]+)",
    r"(\bAND\b\s+[\w'\"]+\s*=\s*[\w'\"]+\s*--)",
    r"('.*'|\".*\")\s*(OR|AND)",
]

def detectar_sql_injection(valor):
    """Detecta patrones comunes de SQL injection"""
    if not isinstance(valor, str):
        return False
    valor_upper = valor.upper()
    for patron in SQL_PATTERNS:
        if re.search(patron, valor_upper, re.IGNORECASE):
            return True
    return False

def sanitizar_input(valor, max_len=500):
    """Sanitiza y limita longitud de inputs"""
    if not isinstance(valor, str):
        return str(valor) if valor else ''
    # Remover caracteres nulos
    valor = valor.replace('\x00', '')
    # Limitar longitud
    valor = valor[:max_len]
    return valor.strip()

def validar_email(email):
    """Valida formato de email"""
    patron = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(patron, email or ''))

def validar_request_json():
    """Valida que el request JSON no tenga SQL injection"""
    if request.is_json:
        datos = request.get_json(silent=True) or {}
        for clave, valor in datos.items():
            if isinstance(valor, str) and detectar_sql_injection(valor):
                return False, f"Input inválido en campo: {clave}"
    return True, None

# ── XSS PREVENTION ────────────────────────────────
def escapar_html(texto):
    """Escapa caracteres HTML peligrosos"""
    if not isinstance(texto, str):
        return texto
    return (texto
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#x27;'))

# ── SESSION VALIDATION ─────────────────────────────
def login_requerido(f):
    """Decorator: requiere sesión activa"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            return jsonify({'error': 'No autorizado. Inicia sesión.'}), 401
        return f(*args, **kwargs)
    return wrapper

def validar_sesion_usuario(usuario_id_param):
    """Verifica que el usuario solo acceda a sus propios datos"""
    if 'usuario_id' not in session:
        return False
    return str(session['usuario_id']) == str(usuario_id_param)

# ── HEADERS DE SEGURIDAD ───────────────────────────
def aplicar_seguridad(app):
    """Aplica configuraciones de seguridad globales a la app Flask"""
    
    @app.after_request
    def agregar_headers_seguridad(response):
        # Prevenir clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        # Prevenir MIME sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # XSS Protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # No cachear datos sensibles
        if request.path.startswith('/api') or request.is_json:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
        return response

    @app.before_request
    def validar_request_global():
        # Bloquear métodos no permitidos en rutas sensibles
        rutas_solo_post = ['/login', '/registro', '/guardar_interes']
        if request.path in rutas_solo_post and request.method not in ['POST', 'OPTIONS']:
            return jsonify({'error': 'Método no permitido'}), 405
        
        # Limitar tamaño de requests (5MB max)
        if request.content_length and request.content_length > 5 * 1024 * 1024:
            return jsonify({'error': 'Request demasiado grande'}), 413

        # Bloquear User-Agents de bots/scanners conocidos
        ua = request.headers.get('User-Agent', '').lower()
        bots_bloqueados = ['sqlmap', 'nikto', 'nmap', 'masscan', 'dirbuster', 'burpsuite']
        if any(bot in ua for bot in bots_bloqueados):
            return jsonify({'error': 'Acceso denegado'}), 403

    print("✅ Seguridad aplicada correctamente")