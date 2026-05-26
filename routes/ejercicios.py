from flask import Blueprint, jsonify, request, session

ejercicios_bp = Blueprint('ejercicios', __name__)

def get_mysql():
    from app import mysql
    return mysql

# ── MATERIAS ──────────────────────────────────────
@ejercicios_bp.route('/materias', methods=['GET'])
def get_materias():
    mysql = get_mysql()
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre, descripcion FROM materias")
    filas = cur.fetchall()
    cur.close()
    return jsonify([
        {'id': f[0], 'nombre': f[1], 'descripcion': f[2]}
        for f in filas
    ]), 200

# ── EJERCICIOS POR TEMA ────────────────────────────
@ejercicios_bp.route('/ejercicios/<int:tema_id>', methods=['GET'])
def get_ejercicios(tema_id):
    mysql = get_mysql()
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, pregunta, dificultad
        FROM ejercicios WHERE tema_id = %s
    """, (tema_id,))
    filas = cur.fetchall()
    cur.close()
    return jsonify([
        {'id': f[0], 'pregunta': f[1], 'dificultad': f[2]}
        for f in filas
    ]), 200

# ── GUARDAR RESULTADO ─────────────────────────────
@ejercicios_bp.route('/responder', methods=['POST'])
def responder():
    datos        = request.json
    usuario_id   = session.get('usuario_id')
    ejercicio_id = datos.get('ejercicio_id')
    respuesta    = datos.get('respuesta', '').strip().lower()

    mysql = get_mysql()
    cur = mysql.connection.cursor()
    cur.execute("SELECT respuesta_correcta FROM ejercicios WHERE id = %s", (ejercicio_id,))
    fila = cur.fetchone()

    if not fila:
        cur.close()
        return jsonify({'error': 'Ejercicio no encontrado'}), 404

    correcto = (respuesta == fila[0].strip().lower())

    cur.execute("""
        INSERT INTO resultados (usuario_id, ejercicio_id, respuesta_usuario, es_correcto)
        VALUES (%s, %s, %s, %s)
    """, (usuario_id, ejercicio_id, respuesta, correcto))
    mysql.connection.commit()
    cur.close()

    return jsonify({
        'correcto': correcto,
        'mensaje':  '¡Correcto! 🎉' if correcto else f'Incorrecto. La respuesta era: {fila[0]}'
    }), 200

# ── GUARDAR PLAN DE ESTUDIO ────────────────────────
@ejercicios_bp.route('/guardar_plan', methods=['POST'])
def guardar_plan():
    datos      = request.json
    usuario_id = session.get('usuario_id', 1)
    materia    = datos.get('materia', '')
    interes    = datos.get('interes', '')
    plan       = datos.get('plan', '')

    mysql = get_mysql()
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            INSERT INTO planes_estudio (usuario_id, materia, interes, plan_completo)
            VALUES (%s, %s, %s, %s)
        """, (usuario_id, materia, interes, plan))
        mysql.connection.commit()
        return jsonify({'mensaje': 'Plan guardado correctamente'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cur.close()

# ── OBTENER PLANES DEL USUARIO ─────────────────────
@ejercicios_bp.route('/mis_planes', methods=['GET'])
def mis_planes():
    usuario_id = session.get('usuario_id', 1)
    mysql = get_mysql()
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, materia, interes, fecha
        FROM planes_estudio
        WHERE usuario_id = %s
        ORDER BY fecha DESC
    """, (usuario_id,))
    planes = cur.fetchall()
    cur.close()
    return jsonify([
        {'id': p[0], 'materia': p[1], 'interes': p[2], 'fecha': str(p[3])}
        for p in planes
    ]), 200


# ── ACTUALIZAR TIPO DE APRENDIZAJE ─────────────────
@ejercicios_bp.route('/actualizar_perfil', methods=['POST'])
def actualizar_perfil():
    datos             = request.json
    usuario_id        = session.get('usuario_id', 1)
    tipo_aprendizaje  = datos.get('tipo_aprendizaje')
    mensajes          = datos.get('mensajes_analizados', 0)

    mysql = get_mysql()
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            UPDATE usuarios
            SET tipo_aprendizaje = %s, mensajes_analizados = %s
            WHERE id = %s
        """, (tipo_aprendizaje, mensajes, usuario_id))
        mysql.connection.commit()
        return jsonify({'mensaje': 'Perfil actualizado'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        cur.close()