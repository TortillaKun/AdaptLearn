from flask import Blueprint, request, jsonify, session
from groq import Groq
from config import Config
import requests
import uuid
import json
import re
import hashlib
from datetime import datetime

chat_bp = Blueprint('chat', __name__)

SYSTEM_PROMPT = """Eres AdaptLearn, un tutor de IA educativo especializado en aprendizaje personalizado.

════════════════════════════════════════
RESTRICCIONES DE DOMINIO
════════════════════════════════════════
Tu única función es ENSEÑAR y AYUDAR A APRENDER cualquier tema con enfoque educativo.

PERMITIDO: matemáticas, ciencias, programación, historia, arte, música, idiomas, etc.
NO PERMITIDO: contenido ofensivo, tareas sin explicar, entretenimiento puro, información dañina.

CÓMO RECHAZAR: "Eso está fuera de mi área como tutor educativo 😊 Pero puedo ayudarte a aprender sobre [tema relacionado]. ¿Te interesa?"

════════════════════════════════════════
DETECCIÓN DE TIPO DE CONTENIDO
════════════════════════════════════════
[TIPO: CODIGO] → programación, desarrollo
[TIPO: MATEMATICA] → cálculos, álgebra, estadística
[TIPO: CIENCIA] → biología, química, física, medicina
[TIPO: HUMANIDADES] → historia, literatura, filosofía
[TIPO: IDIOMA] → aprender un idioma
[TIPO: GENERAL] → cualquier otro tema educativo

════════════════════════════════════════
FORMATO DE RESPUESTA — MUY IMPORTANTE
════════════════════════════════════════
DIVIDE tu respuesta en secciones claras usando este separador:
---PARTE---

Ejemplo:
[TIPO: CODIGO]
[PERFIL: VISUAL]

¡Hola! Me alegra que quieras aprender Python 🐍

---PARTE---

**¿Qué es Python?**
Python es un lenguaje fácil de leer...

---PARTE---

Vamos con tu primer programa:
```python
print("¡Hola Mundo!")
```

════════════════════════════════════════
DETECCIÓN DE ESTILO DE APRENDIZAJE
════════════════════════════════════════
- VISUAL: "ver", "mostrar", "imagen", "gráfico", "esquema"
- AUDITIVO: "explicar", "escuchar", "contar", "hablar"
- LECTOR: "leer", "texto", "definición", "apuntes", "libro"
- KINESTÉSICO: "hacer", "practicar", "ejercicio", "paso a paso"

Incluye en CADA respuesta: [PERFIL: VISUAL/AUDITIVO/LECTOR/KINESTÉSICO]

════════════════════════════════════════
PLAN PERSONALIZADO
════════════════════════════════════════
[PLAN_INICIO]
MATERIA: {materia}
INTERES: {interés}
ESTILO: {estilo}
SEMANA 1: {título}
- {actividad}
- {actividad}
- {actividad}
SEMANA 2: {título}
- {actividad}
- {actividad}
SEMANA 3: {título}
- {actividad}
SEMANA 4: {título}
- {actividad}
[PLAN_FIN]

FUENTES:
[FUENTES_INICIO]
- {Título} | {Autor} | {URL}
[FUENTES_FIN]

════════════════════════════════════════
REGLAS
════════════════════════════════════════
- Sé cálido y cercano. Tutea al estudiante
- Responde siempre en español
- SIEMPRE divide con ---PARTE--- para no abrumar
- Si detectas código, usa bloques formateados
- Nunca hagas la tarea sin explicar
- Máximo 3 conceptos nuevos por sección"""


# ── NIVELES DE DIFICULTAD ──────────────────────────
NIVELES_CONFIG = {
    1: {
        'nombre': 'Principiante',
        'descripcion': 'Ejercicio MUY básico para alguien que NUNCA ha visto el tema. Una sola idea simple.',
        'programacion': 'Solo print() con texto fijo. Sin variables. Ej: print("Hola")',
        'matematicas': 'Suma o resta de dos números concretos. Sin variables. Ej: ¿Cuánto es 5+3?',
        'medicina': 'Nombrar o identificar una sola parte del cuerpo o concepto básico. Ej: ¿Qué es el corazón?',
        'biologia': 'Identificar qué es una célula o un ser vivo. Pregunta de sí/no o definición simple.',
        'quimica': 'Nombrar un elemento de la tabla periódica. ¿Qué es el agua?',
        'fisica': 'Definir qué es la velocidad o la fuerza con palabras simples.',
        'historia': 'Identificar una fecha o personaje histórico muy conocido.',
        'general': 'Pregunta de definición básica con una sola respuesta de una oración.'
    },
    2: {
        'nombre': 'Básico',
        'descripcion': 'Ejercicio elemental. El estudiante ya conoce los conceptos fundamentales.',
        'programacion': 'Variable + print. Ej: nombre = "Juan", print(nombre)',
        'matematicas': 'Multiplicación o división simple. Ecuación con una variable. Ej: x + 5 = 10',
        'medicina': 'Identificar la función de un órgano. Ej: ¿Para qué sirven los pulmones?',
        'biologia': 'Diferencia entre célula animal y vegetal. Partes de una célula.',
        'quimica': 'Símbolo de un elemento. Estados de la materia.',
        'fisica': 'Calcular velocidad con fórmula simple v=d/t con números dados.',
        'historia': 'Relacionar un evento con su época o consecuencia directa.',
        'general': 'Pregunta de comprensión que requiere una respuesta de 2-3 oraciones.'
    },
    3: {
        'nombre': 'Intermedio',
        'descripcion': 'Ejercicio de dificultad media. Requiere combinar 2-3 conceptos.',
        'programacion': 'if/else + variables. Bucle for simple. Listas básicas.',
        'matematicas': 'Sistema de 2 ecuaciones. Función lineal. Porcentajes aplicados.',
        'medicina': 'Explicar un proceso fisiológico simple. Ej: ¿Cómo funciona la digestión?',
        'biologia': 'Explicar el proceso de fotosíntesis o mitosis paso a paso.',
        'quimica': 'Balancear una ecuación química simple. Tipos de enlace.',
        'fisica': 'Problema de cinemática con 2 pasos. Leyes de Newton aplicadas.',
        'historia': 'Analizar causas y consecuencias de un evento histórico.',
        'general': 'Pregunta de aplicación que requiere razonamiento y ejemplos.'
    },
    4: {
        'nombre': 'Avanzado',
        'descripcion': 'Ejercicio complejo que combina varios conceptos del tema.',
        'programacion': 'Funciones con parámetros. Diccionarios. Manejo de errores. Recursión básica.',
        'matematicas': 'Derivadas simples. Integrales básicas. Matrices 2x2.',
        'medicina': 'Relacionar síntomas con diagnóstico. Explicar un mecanismo de enfermedad.',
        'biologia': 'Explicar herencia genética. Cadena alimenticia compleja.',
        'quimica': 'Estequiometría. Reacciones de oxidación-reducción.',
        'fisica': 'Trabajo y energía. Movimiento circular. Electrostática básica.',
        'historia': 'Comparar dos períodos o civilizaciones. Análisis de fuentes.',
        'general': 'Análisis profundo que requiere síntesis de múltiples conceptos.'
    },
    5: {
        'nombre': 'Experto',
        'descripcion': 'Ejercicio de alto nivel. Problemas reales y complejos del tema.',
        'programacion': 'POO completa. Algoritmos de ordenamiento. APIs. Manejo de archivos.',
        'matematicas': 'Problemas multi-paso. Demostraciones. Cálculo avanzado.',
        'medicina': 'Caso clínico complejo. Diagnóstico diferencial. Plan de tratamiento.',
        'biologia': 'Ingeniería genética. Ecosistemas complejos. Evolución molecular.',
        'quimica': 'Síntesis orgánica. Termodinámica química. Cinética de reacciones.',
        'fisica': 'Mecánica cuántica básica. Relatividad. Física del estado sólido.',
        'historia': 'Historiografía. Interpretación de fuentes primarias. Ensayo argumentativo.',
        'general': 'Síntesis de conocimiento avanzado. Problemas abiertos. Investigación.'
    }
}


def buscar_openalex(tema, limite=3):
    try:
        res = requests.get("https://api.openalex.org/works", params={
            'search': tema, 'per_page': limite, 'sort': 'cited_by_count:desc'
        }, timeout=5)
        data = res.json()
        resultados = []
        for item in data.get('results', []):
            titulo  = item.get('title', 'Sin título')
            autores = ', '.join([a.get('author', {}).get('display_name', '') for a in item.get('authorships', [])[:2]])
            link    = item.get('primary_location', {}).get('landing_page_url') or f"https://openalex.org/{item.get('id','').split('/')[-1]}"
            resultados.append({'titulo': titulo, 'autores': autores or 'Desconocido', 'link': link, 'anio': item.get('publication_year', ''), 'fuente': 'OpenAlex'})
        return resultados
    except:
        return []


def buscar_semantic(tema, limite=3):
    try:
        res = requests.get("https://api.semanticscholar.org/graph/v1/paper/search", params={
            'query': tema, 'limit': limite, 'fields': 'title,authors,year,externalIds,openAccessPdf'
        }, timeout=5)
        data = res.json()
        resultados = []
        for item in data.get('data', []):
            titulo  = item.get('title', 'Sin título')
            autores = ', '.join([a.get('name', '') for a in item.get('authors', [])[:2]])
            pdf     = item.get('openAccessPdf') or {}
            link    = pdf.get('url') or (f"https://doi.org/{item.get('externalIds',{}).get('DOI')}" if item.get('externalIds',{}).get('DOI') else 'https://www.semanticscholar.org')
            resultados.append({'titulo': titulo, 'autores': autores or 'Desconocido', 'link': link, 'anio': item.get('year', ''), 'fuente': 'Semantic Scholar'})
        return resultados
    except:
        return []


def obtener_fuentes(tema):
    todas = buscar_openalex(tema, 3) + buscar_semantic(tema, 3)
    if not todas:
        return ""
    texto = "\n\n--- FUENTES ACADÉMICAS REALES ---\n"
    for f in todas:
        texto += f"- {f['titulo']} | {f['autores']} ({f['anio']}) | {f['link']} [{f['fuente']}]\n"
    return texto + "--- FIN FUENTES ---\n"


def detectar_materia(texto):
    materias = {
        'Medicina':     ['medicina', 'médico', 'anatomia', 'anatomía', 'bioquimica', 'bioquímica',
                         'enfermeria', 'enfermería', 'salud', 'cuerpo humano', 'organo', 'órgano',
                         'hueso', 'musculo', 'músculo', 'sangre', 'corazon', 'corazón', 'celula', 'célula'],
        'Algebra':      ['algebra', 'álgebra', 'vectores', 'matrices', 'vector', 'matriz',
                         'espacio vectorial', 'transformacion lineal', 'determinante'],
        'Calculo':      ['calculo', 'cálculo', 'derivada', 'integral', 'limite', 'límite',
                         'derivar', 'integrar', 'diferencial', 'continuidad'],
        'Biologia':     ['biologia', 'biología', 'celula', 'célula', 'genetica', 'genética',
                         'ecosistema', 'organismo', 'evolucion', 'evolución', 'adn', 'arn',
                         'fotosintesis', 'fotosíntesis', 'mitosis', 'meiosis'],
        'Quimica':      ['quimica', 'química', 'elemento', 'reaccion', 'reacción', 'compuesto',
                         'atomo', 'átomo', 'molecula', 'molécula', 'tabla periodica', 'enlace',
                         'oxidacion', 'oxidación', 'acido', 'ácido', 'base'],
        'Fisica':       ['fisica', 'física', 'fuerza', 'energia', 'energía', 'movimiento',
                         'velocidad', 'aceleracion', 'aceleración', 'gravedad', 'newton',
                         'electricidad', 'magnetismo', 'onda', 'optica', 'óptica'],
        'Historia':     ['historia', 'historico', 'histórico', 'guerra', 'civilizacion', 'civilización',
                         'revolucion', 'revolución', 'independencia', 'colonia', 'ancient',
                         'prehistoria', 'edad media', 'renacimiento'],
        'Programacion': ['programacion', 'programación', 'codigo', 'código', 'python', 'javascript',
                         'software', 'c++', 'java', 'html', 'css', 'algoritmo', 'variable',
                         'funcion', 'función', 'bucle', 'loop', 'array', 'objeto', 'clase',
                         'programar', 'desarrollar', 'web', 'aplicacion', 'aplicación'],
        'Matematicas':  ['matematicas', 'matemáticas', 'ecuacion', 'ecuación', 'funcion', 'función',
                         'numero', 'número', 'suma', 'resta', 'multiplicacion', 'multiplicación',
                         'division', 'división', 'fraccion', 'fracción', 'porcentaje', 'geometria',
                         'geometría', 'trigonometria', 'trigonometría', 'estadistica', 'estadística'],
        'Arte':         ['arte', 'pintura', 'dibujo', 'escultura', 'diseño', 'color', 'perspectiva',
                         'acuarela', 'oleo', 'óleo', 'boceto', 'composicion', 'composición'],
        'Musica':       ['musica', 'música', 'nota musical', 'acorde', 'ritmo', 'melodia', 'melodía',
                         'instrumento', 'guitarra', 'piano', 'bateria', 'batería', 'solfeo'],
        'Idiomas':      ['ingles', 'inglés', 'frances', 'francés', 'aleman', 'alemán', 'idioma',
                         'lenguaje', 'gramatica', 'gramática', 'vocabulario', 'pronunciacion'],
    }
    t = texto.lower()
    # Buscar coincidencia exacta primero
    for materia, palabras in materias.items():
        if any(p in t for p in palabras):
            return materia
    # Si no encontró nada, intentar con el contexto de "aprender X"
    import re
    match = re.search(r'aprender?\s+(\w+)', t)
    if match:
        tema = match.group(1)
        for materia, palabras in materias.items():
            if any(p in tema for p in palabras):
                return materia
    return 'General'


def guardar_mensaje_db(usuario_id, sesion_id, rol, mensaje):
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO historial_chat (usuario_id, sesion_id, rol, mensaje) VALUES (%s, %s, %s, %s)",
                    (usuario_id, sesion_id, rol, mensaje))
        mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"Error guardando mensaje: {e}")


def crear_o_actualizar_sesion(usuario_id, sesion_id, titulo, materia, total_mensajes):
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM sesiones_chat WHERE sesion_id = %s", (sesion_id,))
        existe = cur.fetchone()
        if existe:
            cur.execute("UPDATE sesiones_chat SET fecha_ultimo=%s, total_mensajes=%s, materia=%s, titulo=%s WHERE sesion_id=%s",
                        (datetime.now(), total_mensajes, materia, titulo, sesion_id))
        else:
            cur.execute("INSERT INTO sesiones_chat (usuario_id, sesion_id, titulo, materia, total_mensajes) VALUES (%s,%s,%s,%s,%s)",
                        (usuario_id, sesion_id, titulo, materia, total_mensajes))
        mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"Error sesión: {e}")


def actualizar_estilos_usuario(usuario_id, estilos_acumulados):
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        if estilos_acumulados:
            estilo_dominante = max(estilos_acumulados, key=estilos_acumulados.get)
            cur.execute("UPDATE usuarios SET tipo_aprendizaje=%s WHERE id=%s", (estilo_dominante, usuario_id))
            mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"Error estilos: {e}")


def obtener_interes_usuario(usuario_id):
    """Obtiene el interés del usuario desde la BD"""
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("SELECT interes FROM usuarios WHERE id=%s", (usuario_id,))
        fila = cur.fetchone()
        cur.close()
        return fila[0] if fila and fila[0] else 'general'
    except:
        return 'general'


def obtener_ejercicios_vistos(usuario_id, materia, nivel):
    """Obtiene los títulos de ejercicios ya vistos para evitar repetición"""
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT titulo FROM ejercicios_vistos
            WHERE usuario_id=%s AND materia=%s AND nivel=%s
            ORDER BY fecha DESC LIMIT 20
        """, (usuario_id, materia, nivel))
        filas = cur.fetchall()
        cur.close()
        return [f[0] for f in filas if f[0]]
    except:
        return []


def guardar_ejercicio_visto(usuario_id, materia, nivel, titulo, ejercicio_hash):
    """Guarda un ejercicio como visto para no repetirlo"""
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO ejercicios_vistos (usuario_id, materia, nivel, titulo, ejercicio_hash)
            VALUES (%s, %s, %s, %s, %s)
        """, (usuario_id, materia, nivel, titulo, ejercicio_hash))
        mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"Error guardando ejercicio visto: {e}")


# ── CHAT IA ────────────────────────────────────────
@chat_bp.route('/chat_ia', methods=['POST'])
def chat_ia():
    datos          = request.json
    mensajes       = datos.get('mensajes', [])
    sesion_id      = datos.get('sesion_id', str(uuid.uuid4()))
    usuario_id     = session.get('usuario_id', 1)
    estilos_sesion = datos.get('estilos_sesion', {'VISUAL':0,'AUDITIVO':0,'LECTOR':0,'KINESTÉSICO':0})

    try:
        cliente = Groq(api_key=Config.GROQ_API_KEY)
        ultimo  = mensajes[-1]['content']
        materia = detectar_materia(ultimo)

        palabras_clave = ['aprender', 'estudiar', 'entender', 'medicina', 'algebra', 'calculo',
                          'biologia', 'quimica', 'fisica', 'historia', 'programacion', 'python',
                          'javascript', 'matematicas', 'ecuacion']
        fuentes_extra = obtener_fuentes(ultimo) if any(p in ultimo.lower() for p in palabras_clave) else ""

        historial = [{"role": "system", "content": SYSTEM_PROMPT + fuentes_extra}]
        for msg in mensajes:
            historial.append({"role": msg['role'], "content": msg['content']})

        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=historial,
            max_tokens=2000,
            temperature=0.7
        )

        texto = respuesta.choices[0].message.content

        match = re.search(r'\[PERFIL:\s*(VISUAL|AUDITIVO|LECTOR|KINESTÉSICO)\]', texto, re.IGNORECASE)
        estilo_actual = match.group(1).upper() if match else None

        if estilo_actual and estilo_actual in estilos_sesion:
            estilos_sesion[estilo_actual] = estilos_sesion.get(estilo_actual, 0) + 1

        guardar_mensaje_db(usuario_id, sesion_id, 'user', ultimo)
        guardar_mensaje_db(usuario_id, sesion_id, 'assistant', texto)

        titulo = f"Aprendizaje de {materia}" if materia else (ultimo[:50] + '...' if len(ultimo) > 50 else ultimo)
        crear_o_actualizar_sesion(usuario_id, sesion_id, titulo, materia, len(mensajes) + 1)
        actualizar_estilos_usuario(usuario_id, estilos_sesion)

        partes = [p.strip() for p in texto.split('---PARTE---') if p.strip()]

        return jsonify({
            'respuesta':      texto,
            'partes':         partes,
            'sesion_id':      sesion_id,
            'estilo_actual':  estilo_actual,
            'estilos_sesion': estilos_sesion,
            'materia':        materia
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── GENERADOR DE EJERCICIOS ÚNICO CON INTERÉS ─────
@chat_bp.route('/generar_ejercicio', methods=['POST'])
def generar_ejercicio():
    datos      = request.json
    materia    = datos.get('materia', 'programación')
    estilo     = datos.get('estilo', 'GENERAL')
    nivel      = datos.get('nivel', 1)
    contexto   = datos.get('contexto', '')
    usuario_id = session.get('usuario_id', 1)

    # Obtener nivel numérico
    try:
        nivel_num = int(nivel)
    except:
        nivel_num = 1
    nivel_num = max(1, min(5, nivel_num))

    config_nivel = NIVELES_CONFIG[nivel_num]

    # Obtener interés del usuario desde la BD
    interes = obtener_interes_usuario(usuario_id)

    # Obtener ejercicios ya vistos para NO repetir
    vistos = obtener_ejercicios_vistos(usuario_id, materia, nivel_num)
    vistos_texto = ''
    if vistos:
        vistos_texto = f"\n\nEJERCICIOS YA DADOS (NO REPETIR NINGUNO DE ESTOS):\n"
        for v in vistos[-10:]:  # últimos 10
            vistos_texto += f"- {v}\n"
        vistos_texto += "El nuevo ejercicio DEBE ser completamente diferente a todos los anteriores.\n"

    try:
        cliente = Groq(api_key=Config.GROQ_API_KEY)

        # Detectar tipo y descripción específica para la materia
        ml = materia.lower()
        if any(x in ml for x in ['program','python','java','codigo','código','software','web','html']):
            desc_esp   = config_nivel.get('programacion', config_nivel['descripcion'])
            tipo_sug   = 'codigo'
            lang_sug   = 'python'
        elif any(x in ml for x in ['mat','algebra','álgebra','calculo','cálculo','estadis']):
            desc_esp   = config_nivel.get('matematicas', config_nivel['descripcion'])
            tipo_sug   = 'matematica'
            lang_sug   = 'matematica'
        elif any(x in ml for x in ['medic','anatom','salud','enfermer','farmac']):
            desc_esp   = config_nivel.get('medicina', config_nivel['descripcion'])
            tipo_sug   = 'texto'
            lang_sug   = 'texto'
        elif any(x in ml for x in ['biolog','célula','celula','genét']):
            desc_esp   = config_nivel.get('biologia', config_nivel['descripcion'])
            tipo_sug   = 'texto'
            lang_sug   = 'texto'
        elif any(x in ml for x in ['quim','átomo','atomo','molecul']):
            desc_esp   = config_nivel.get('quimica', config_nivel['descripcion'])
            tipo_sug   = 'texto'
            lang_sug   = 'texto'
        elif any(x in ml for x in ['fisic','fuerza','energi','velocid']):
            desc_esp   = config_nivel.get('fisica', config_nivel['descripcion'])
            tipo_sug   = 'matematica'
            lang_sug   = 'matematica'
        elif any(x in ml for x in ['histor','guerra','civiliz','revoluci']):
            desc_esp   = config_nivel.get('historia', config_nivel['descripcion'])
            tipo_sug   = 'texto'
            lang_sug   = 'texto'
        else:
            desc_esp   = config_nivel.get('general', config_nivel['descripcion'])
            tipo_sug   = 'texto'
            lang_sug   = 'texto'

        prompt = f"""Eres un tutor experto en {materia}. Crea UN ejercicio práctico NUEVO y ÚNICO.

MATERIA: {materia}
NIVEL {nivel_num} — {config_nivel['nombre']}
DIFICULTAD ESPERADA: {desc_esp}
INTERÉS DEL ESTUDIANTE: {interes}
TIPO DE EJERCICIO: {tipo_sug}
{vistos_texto}

REGLAS OBLIGATORIAS — DEBES SEGUIRLAS TODAS:
1. El ejercicio es EXCLUSIVAMENTE de {materia}. NO cambies a otra materia.
2. CONECTA el ejercicio con el interés "{interes}" del estudiante:
   - Fútbol: usa jugadores, goles, equipos, partidos, estadios
   - Música: usa canciones, artistas, notas, conciertos, géneros
   - Videojuegos: usa personajes, puntos, vidas, niveles, misiones
   - Cocina: usa ingredientes, recetas, temperaturas, porciones
   - Baloncesto/Voleibol: usa jugadores, canastas, sets, puntos
   - Arte/Cine: usa obras, artistas, películas, técnicas
   - Adaptación creativa para cualquier otro interés
3. Nivel {nivel_num}: {desc_esp}
4. COMPLETAMENTE diferente a los ejercicios ya vistos
5. Tipo correcto según materia:
   - Programación → tipo "codigo", incluye código incompleto para completar
   - Matemáticas/Física → tipo "matematica", incluye números concretos
   - Medicina/Biología/Historia/Química → tipo "texto", pregunta directa y clara

Responde SOLO en JSON sin texto adicional:
{{
  "tipo": "{tipo_sug}",
  "titulo": "Título breve relacionado con {interes} y {materia}",
  "instruccion": "Instrucción específica de {materia}. Clara y directa. Usa {interes} como contexto.",
  "ejemplo_entrada": "Para código: código incompleto. Para matemática: datos del problema. Para texto: contexto extra o vacío.",
  "pista": "Pista general sin revelar la respuesta",
  "pistas_extra": ["Pista más específica", "Un paso resuelto", "Casi la solución completa"],
  "respuesta_correcta": "Respuesta completa y correcta",
  "explicacion": "Paso a paso detallado de cómo se resuelve",
  "lenguaje": "{lang_sug}"
}}"""

        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.9  # Alta temperatura para más variedad
        )

        texto = respuesta.choices[0].message.content
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            ejercicio = json.loads(match.group())

            # Guardar como visto para no repetir
            titulo_ej = ejercicio.get('titulo', 'Ejercicio')
            hash_ej   = hashlib.md5(f"{titulo_ej}{materia}{nivel_num}".encode()).hexdigest()[:16]
            guardar_ejercicio_visto(usuario_id, materia, nivel_num, titulo_ej, hash_ej)

            # Agregar info de nivel al ejercicio
            ejercicio['nivel_num']    = nivel_num
            ejercicio['nivel_nombre'] = config_nivel['nombre']
            ejercicio['interes']      = interes

            return jsonify(ejercicio), 200

        return jsonify({'error': 'No se pudo generar el ejercicio'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── EVALUAR RESPUESTA ──────────────────────────────
@chat_bp.route('/evaluar_respuesta', methods=['POST'])
def evaluar_respuesta():
    datos             = request.json
    ejercicio         = datos.get('ejercicio', '')
    respuesta_usuario = datos.get('respuesta_usuario', '')
    tipo              = datos.get('tipo', 'texto')
    materia           = datos.get('materia', '')

    try:
        cliente = Groq(api_key=Config.GROQ_API_KEY)

        prompt = f"""Evalúa la respuesta del estudiante de forma constructiva y motivadora.

EJERCICIO: {ejercicio}
RESPUESTA DEL ESTUDIANTE: {respuesta_usuario}
TIPO: {tipo}
MATERIA: {materia}

Criterios de evaluación:
- 90-100%: Correcto y completo
- 80-89%: Correcto con pequeños detalles
- 60-79%: Parcialmente correcto, falta algo importante
- 0-59%: Incorrecto o incompleto

Responde SOLO en JSON:
{{
  "correcto": true o false,
  "puntaje": número del 0 al 100,
  "mensaje": "Mensaje motivador personalizado",
  "errores": "Descripción específica de errores si los hay",
  "correccion": "Solución correcta con explicación paso a paso",
  "siguiente_paso": "Qué debería practicar ahora"
}}"""

        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.4
        )

        texto = respuesta.choices[0].message.content
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            return jsonify(json.loads(match.group())), 200
        return jsonify({'error': 'No se pudo evaluar'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── EJECUTAR CÓDIGO ────────────────────────────────
@chat_bp.route('/ejecutar_codigo', methods=['POST'])
def ejecutar_codigo():
    datos    = request.json
    codigo   = datos.get('codigo', '')
    lenguaje = datos.get('lenguaje', 'python')

    try:
        cliente = Groq(api_key=Config.GROQ_API_KEY)

        prompt = f"""Simula la ejecución del siguiente código en {lenguaje} y muestra exactamente qué imprimiría.

CÓDIGO:
```{lenguaje}
{codigo}
```

Si hay errores, muestra el error exacto.
Si funciona, muestra el output exacto línea por línea.

Responde SOLO en JSON:
{{
  "output": "Lo que imprimiría el programa",
  "error": "El error si lo hay, vacío si funciona",
  "exitoso": true o false,
  "explicacion": "Breve explicación de qué hizo el código"
}}"""

        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.1
        )

        texto = respuesta.choices[0].message.content
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            return jsonify(json.loads(match.group())), 200
        return jsonify({'error': 'No se pudo ejecutar'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── SESIONES ───────────────────────────────────────
@chat_bp.route('/mis_sesiones', methods=['GET'])
def mis_sesiones():
    usuario_id = session.get('usuario_id', 1)
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT sesion_id, titulo, materia, fecha, fecha_ultimo, total_mensajes
            FROM sesiones_chat WHERE usuario_id=%s
            ORDER BY fecha_ultimo DESC LIMIT 20
        """, (usuario_id,))
        filas = cur.fetchall()
        cur.close()
        return jsonify([{
            'sesion_id':      f[0],
            'titulo':         f[1] or 'Conversación',
            'materia':        f[2] or '',
            'fecha_inicio':   str(f[3]),
            'fecha_ultimo':   str(f[4]),
            'total_mensajes': f[5] or 0
        } for f in filas]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/sesion/<sid>', methods=['GET'])
def ver_sesion(sid):
    usuario_id = session.get('usuario_id', 1)
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("SELECT rol, mensaje, fecha FROM historial_chat WHERE usuario_id=%s AND sesion_id=%s ORDER BY fecha ASC",
                    (usuario_id, sid))
        mensajes = cur.fetchall()
        cur.close()
        return jsonify([{'rol': m[0], 'mensaje': m[1], 'fecha': str(m[2])} for m in mensajes]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/eliminar_sesion/<sesion_id>', methods=['DELETE'])
def eliminar_sesion(sesion_id):
    usuario_id = session.get('usuario_id', 1)
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM historial_chat WHERE sesion_id=%s AND usuario_id=%s", (sesion_id, usuario_id))
        cur.execute("DELETE FROM sesiones_chat WHERE sesion_id=%s AND usuario_id=%s", (sesion_id, usuario_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({'mensaje': 'Sesión eliminada'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── RENDIMIENTO ────────────────────────────────────
@chat_bp.route('/mi_rendimiento', methods=['GET'])
def mi_rendimiento():
    usuario_id = session.get('usuario_id', 1)
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM sesiones_chat WHERE usuario_id=%s", (usuario_id,))
        total_sesiones = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM historial_chat WHERE usuario_id=%s AND rol='user'", (usuario_id,))
        total_mensajes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM planes_estudio WHERE usuario_id=%s", (usuario_id,))
        total_planes = cur.fetchone()[0]
        cur.execute("""SELECT materia, COUNT(*) as v FROM sesiones_chat
            WHERE usuario_id=%s AND materia!='' AND materia IS NOT NULL
            GROUP BY materia ORDER BY v DESC LIMIT 5""", (usuario_id,))
        materias = [{'materia': f[0], 'veces': f[1]} for f in cur.fetchall()]
        cur.execute("SELECT tipo_aprendizaje, nombre FROM usuarios WHERE id=%s", (usuario_id,))
        fila = cur.fetchone()
        tipo   = fila[0] if fila else 'sin detectar'
        nombre = fila[1] if fila else 'Estudiante'
        cur.execute("SELECT COUNT(*) FROM historial_chat WHERE usuario_id=%s AND rol='assistant'", (usuario_id,))
        total_ai = cur.fetchone()[0] or 1
        estilos_conteo = {}
        for estilo in ['VISUAL', 'AUDITIVO', 'LECTOR', 'KINESTÉSICO']:
            cur.execute("SELECT COUNT(*) FROM historial_chat WHERE usuario_id=%s AND rol='assistant' AND mensaje LIKE %s",
                        (usuario_id, f'%[PERFIL: {estilo}]%'))
            conteo = cur.fetchone()[0]
            estilos_conteo[estilo] = round((conteo / total_ai) * 100) if total_ai > 0 else 0
        cur.close()
        return jsonify({
            'nombre': nombre, 'total_sesiones': total_sesiones,
            'total_mensajes': total_mensajes, 'total_planes': total_planes,
            'materias': materias, 'tipo_aprendizaje': tipo,
            'estilos_porcentaje': estilos_conteo
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── PLANES ─────────────────────────────────────────
@chat_bp.route('/mis_planes', methods=['GET'])
def mis_planes():
    usuario_id = session.get('usuario_id', 1)
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, materia, interes, fecha FROM planes_estudio WHERE usuario_id=%s ORDER BY fecha DESC LIMIT 10", (usuario_id,))
        planes = cur.fetchall()
        cur.close()
        return jsonify([{'id': p[0], 'materia': p[1], 'interes': p[2], 'fecha': str(p[3])} for p in planes]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/guardar_plan', methods=['POST'])
def guardar_plan():
    datos      = request.json
    usuario_id = session.get('usuario_id', 1)
    try:
        from app import mysql
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO planes_estudio (usuario_id, materia, interes, plan_completo) VALUES (%s,%s,%s,%s)",
                    (usuario_id, datos.get('materia',''), datos.get('interes',''), datos.get('plan','')))
        mysql.connection.commit()
        cur.close()
        return jsonify({'mensaje': 'Plan guardado'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500