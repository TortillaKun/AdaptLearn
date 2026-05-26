from flask import Blueprint, request, jsonify, session
from groq import Groq
from config import Config
import requests
import uuid
import json
import re
import hashlib
from datetime import datetime

chat_bp = Blueprint("chat", __name__)

def get_db():
    from app import get_db as _get_db
    return _get_db()

SYSTEM_PROMPT = """Eres AdaptLearn, un tutor de IA educativo especializado en aprendizaje personalizado.

Tu única función es ENSEÑAR y AYUDAR A APRENDER cualquier tema con enfoque educativo.
PERMITIDO: matemáticas, ciencias, programación, historia, arte, música, idiomas, etc.
NO PERMITIDO: contenido ofensivo, tareas sin explicar, entretenimiento puro.

FORMATO: Divide respuestas con ---PARTE---
Incluye [TIPO: CODIGO/MATEMATICA/CIENCIA/HUMANIDADES/IDIOMA/GENERAL]
Incluye [PERFIL: VISUAL/AUDITIVO/LECTOR/KINESTÉSICO]

PLAN FORMAT:
[PLAN_INICIO]
MATERIA: x
INTERES: x
ESTILO: x
SEMANA 1: titulo
- actividad
[PLAN_FIN]

[FUENTES_INICIO]
- Titulo | Autor | URL
[FUENTES_FIN]

Responde siempre en español. Sé cálido y cercano."""

NIVELES_CONFIG = {
    1: {"nombre": "Principiante", "descripcion": "Ejercicio MUY básico, una sola idea simple.",
        "programacion": "Solo print() con texto fijo.", "matematicas": "Suma o resta simple.",
        "medicina": "Nombrar una parte del cuerpo.", "biologia": "¿Qué es una célula?",
        "quimica": "Nombrar un elemento.", "fisica": "Definir velocidad con palabras.",
        "historia": "Identificar una fecha histórica.", "general": "Definición básica."},
    2: {"nombre": "Básico", "descripcion": "Ejercicio elemental con conceptos fundamentales.",
        "programacion": "Variable + print.", "matematicas": "Ecuación con una variable.",
        "medicina": "Función de un órgano.", "biologia": "Partes de una célula.",
        "quimica": "Símbolo de elemento.", "fisica": "v=d/t con números dados.",
        "historia": "Relacionar evento con época.", "general": "Respuesta de 2-3 oraciones."},
    3: {"nombre": "Intermedio", "descripcion": "Combinar 2-3 conceptos.",
        "programacion": "if/else + bucle.", "matematicas": "Sistema de ecuaciones.",
        "medicina": "Proceso fisiológico.", "biologia": "Fotosíntesis paso a paso.",
        "quimica": "Balancear ecuación.", "fisica": "Problema de cinemática.",
        "historia": "Causas y consecuencias.", "general": "Razonamiento con ejemplos."},
    4: {"nombre": "Avanzado", "descripcion": "Varios conceptos combinados.",
        "programacion": "Funciones + diccionarios.", "matematicas": "Derivadas simples.",
        "medicina": "Síntomas y diagnóstico.", "biologia": "Herencia genética.",
        "quimica": "Estequiometría.", "fisica": "Trabajo y energía.",
        "historia": "Comparar civilizaciones.", "general": "Síntesis de conceptos."},
    5: {"nombre": "Experto", "descripcion": "Problemas reales y complejos.",
        "programacion": "POO + algoritmos.", "matematicas": "Cálculo avanzado.",
        "medicina": "Caso clínico complejo.", "biologia": "Ingeniería genética.",
        "quimica": "Síntesis orgánica.", "fisica": "Mecánica cuántica básica.",
        "historia": "Fuentes primarias.", "general": "Investigación avanzada."}
}


def buscar_openalex(tema, limite=3):
    try:
        res = requests.get("https://api.openalex.org/works",
            params={"search": tema, "per_page": limite, "sort": "cited_by_count:desc"}, timeout=5)
        data = res.json()
        resultados = []
        for item in data.get("results", []):
            titulo  = item.get("title", "Sin título")
            autores = ", ".join([a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])[:2]])
            link    = item.get("primary_location", {}).get("landing_page_url") or f"https://openalex.org/{item.get('id','').split('/')[-1]}"
            resultados.append({"titulo": titulo, "autores": autores or "Desconocido", "link": link,
                                "anio": item.get("publication_year", ""), "fuente": "OpenAlex"})
        return resultados
    except:
        return []


def buscar_semantic(tema, limite=3):
    try:
        res = requests.get("https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": tema, "limit": limite, "fields": "title,authors,year,externalIds,openAccessPdf"}, timeout=5)
        data = res.json()
        resultados = []
        for item in data.get("data", []):
            titulo  = item.get("title", "Sin título")
            autores = ", ".join([a.get("name", "") for a in item.get("authors", [])[:2]])
            pdf     = item.get("openAccessPdf") or {}
            doi     = item.get("externalIds", {}).get("DOI")
            link    = pdf.get("url") or (f"https://doi.org/{doi}" if doi else "https://www.semanticscholar.org")
            resultados.append({"titulo": titulo, "autores": autores or "Desconocido", "link": link,
                                "anio": item.get("year", ""), "fuente": "Semantic Scholar"})
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
        "Medicina":     ["medicina","médico","anatomia","anatomía","salud","cuerpo","organo","órgano","hueso","musculo","músculo","sangre","corazon","corazón"],
        "Algebra":      ["algebra","álgebra","vectores","matrices","vector","matriz","determinante"],
        "Calculo":      ["calculo","cálculo","derivada","integral","limite","límite","diferencial"],
        "Biologia":     ["biologia","biología","celula","célula","genetica","genética","ecosistema","adn","fotosintesis","mitosis"],
        "Quimica":      ["quimica","química","elemento","reaccion","reacción","atomo","átomo","molecula","molécula","acido","ácido"],
        "Fisica":       ["fisica","física","fuerza","energia","energía","velocidad","gravedad","newton","electricidad"],
        "Historia":     ["historia","historico","histórico","guerra","civilizacion","revolucion","independencia"],
        "Programacion": ["programacion","programación","codigo","código","python","javascript","software","algoritmo","variable","funcion","función","bucle","html","css"],
        "Matematicas":  ["matematicas","matemáticas","ecuacion","ecuación","numero","número","suma","resta","fraccion","porcentaje","geometria","trigonometria","estadistica"],
        "Arte":         ["arte","pintura","dibujo","escultura","diseño","color"],
        "Musica":       ["musica","música","nota musical","acorde","ritmo","instrumento"],
        "Idiomas":      ["ingles","inglés","frances","francés","idioma","lenguaje","vocabulario"],
    }
    t = texto.lower()
    for materia, palabras in materias.items():
        if any(p in t for p in palabras):
            return materia
    return "General"


def ejecutar_db(query, params=(), fetchone=False, fetchall=False, commit=False):
    con = get_db()
    cur = con.cursor()
    try:
        cur.execute(query, params)
        if commit:
            con.commit()
            return cur.lastrowid
        if fetchone:
            return cur.fetchone()
        if fetchall:
            return cur.fetchall()
    except Exception as e:
        print(f"DB error: {e}")
        return None
    finally:
        cur.close()
        con.close()


def guardar_mensaje_db(usuario_id, sesion_id, rol, mensaje):
    ejecutar_db("INSERT INTO historial_chat (usuario_id, sesion_id, rol, mensaje) VALUES (%s,%s,%s,%s)",
                (usuario_id, sesion_id, rol, mensaje), commit=True)


def crear_o_actualizar_sesion(usuario_id, sesion_id, titulo, materia, total_mensajes):
    existe = ejecutar_db("SELECT id FROM sesiones_chat WHERE sesion_id=%s", (sesion_id,), fetchone=True)
    if existe:
        ejecutar_db("UPDATE sesiones_chat SET fecha_ultimo=%s,total_mensajes=%s,materia=%s,titulo=%s WHERE sesion_id=%s",
                    (datetime.now(), total_mensajes, materia, titulo, sesion_id), commit=True)
    else:
        ejecutar_db("INSERT INTO sesiones_chat (usuario_id,sesion_id,titulo,materia,total_mensajes) VALUES (%s,%s,%s,%s,%s)",
                    (usuario_id, sesion_id, titulo, materia, total_mensajes), commit=True)


def actualizar_estilos_usuario(usuario_id, estilos):
    if estilos:
        dominante = max(estilos, key=estilos.get)
        ejecutar_db("UPDATE usuarios SET tipo_aprendizaje=%s WHERE id=%s", (dominante, usuario_id), commit=True)


def obtener_interes_usuario(usuario_id):
    fila = ejecutar_db("SELECT interes FROM usuarios WHERE id=%s", (usuario_id,), fetchone=True)
    return fila[0] if fila and fila[0] else "general"


def obtener_ejercicios_vistos(usuario_id, materia, nivel):
    filas = ejecutar_db("""SELECT titulo FROM ejercicios_vistos
        WHERE usuario_id=%s AND materia=%s AND nivel=%s ORDER BY fecha DESC LIMIT 20""",
        (usuario_id, materia, nivel), fetchall=True)
    return [f[0] for f in filas if f and f[0]] if filas else []


def guardar_ejercicio_visto(usuario_id, materia, nivel, titulo, ejercicio_hash):
    ejecutar_db("INSERT INTO ejercicios_vistos (usuario_id,materia,nivel,titulo,ejercicio_hash) VALUES (%s,%s,%s,%s,%s)",
                (usuario_id, materia, nivel, titulo, ejercicio_hash), commit=True)


@chat_bp.route("/chat_ia", methods=["POST"])
def chat_ia():
    datos          = request.json
    mensajes       = datos.get("mensajes", [])
    sesion_id      = datos.get("sesion_id", str(uuid.uuid4()))
    usuario_id     = session.get("usuario_id", 1)
    estilos_sesion = datos.get("estilos_sesion", {"VISUAL":0,"AUDITIVO":0,"LECTOR":0,"KINESTÉSICO":0})

    try:
        cliente = Groq(api_key=Config.GROQ_API_KEY)
        ultimo  = mensajes[-1]["content"]
        materia = detectar_materia(ultimo)

        palabras_clave = ["aprender","estudiar","entender","medicina","algebra","calculo","biologia",
                          "quimica","fisica","historia","programacion","python","matematicas"]
        fuentes_extra = obtener_fuentes(ultimo) if any(p in ultimo.lower() for p in palabras_clave) else ""

        historial = [{"role": "system", "content": SYSTEM_PROMPT + fuentes_extra}]
        for msg in mensajes:
            historial.append({"role": msg["role"], "content": msg["content"]})

        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=historial, max_tokens=2000, temperature=0.7)

        texto = respuesta.choices[0].message.content
        match = re.search(r"\[PERFIL:\s*(VISUAL|AUDITIVO|LECTOR|KINESTÉSICO)\]", texto, re.IGNORECASE)
        estilo_actual = match.group(1).upper() if match else None

        if estilo_actual and estilo_actual in estilos_sesion:
            estilos_sesion[estilo_actual] = estilos_sesion.get(estilo_actual, 0) + 1

        guardar_mensaje_db(usuario_id, sesion_id, "user", ultimo)
        guardar_mensaje_db(usuario_id, sesion_id, "assistant", texto)
        titulo = f"Aprendizaje de {materia}" if materia else (ultimo[:50] + "..." if len(ultimo) > 50 else ultimo)
        crear_o_actualizar_sesion(usuario_id, sesion_id, titulo, materia, len(mensajes)+1)
        actualizar_estilos_usuario(usuario_id, estilos_sesion)

        partes = [p.strip() for p in texto.split("---PARTE---") if p.strip()]
        return jsonify({"respuesta": texto, "partes": partes, "sesion_id": sesion_id,
                        "estilo_actual": estilo_actual, "estilos_sesion": estilos_sesion, "materia": materia}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/generar_ejercicio", methods=["POST"])
def generar_ejercicio():
    datos      = request.json
    materia    = datos.get("materia", "programación")
    estilo     = datos.get("estilo", "GENERAL")
    nivel      = datos.get("nivel", 1)
    contexto   = datos.get("contexto", "")
    usuario_id = session.get("usuario_id", 1)

    try:
        nivel_num    = max(1, min(5, int(nivel)))
    except:
        nivel_num    = 1
    config_nivel = NIVELES_CONFIG[nivel_num]
    interes      = obtener_interes_usuario(usuario_id)
    vistos       = obtener_ejercicios_vistos(usuario_id, materia, nivel_num)
    vistos_texto = ""
    if vistos:
        vistos_texto = "\nEJERCICIOS YA DADOS (NO REPETIR):\n" + "\n".join(f"- {v}" for v in vistos[-10:]) + "\n"

    ml = materia.lower()
    if any(x in ml for x in ["program","python","java","codigo","código","software","html"]):
        desc_esp, tipo_sug, lang_sug = config_nivel.get("programacion", config_nivel["descripcion"]), "codigo", "python"
    elif any(x in ml for x in ["mat","algebra","álgebra","calculo","cálculo"]):
        desc_esp, tipo_sug, lang_sug = config_nivel.get("matematicas", config_nivel["descripcion"]), "matematica", "matematica"
    elif any(x in ml for x in ["medic","anatom","salud"]):
        desc_esp, tipo_sug, lang_sug = config_nivel.get("medicina", config_nivel["descripcion"]), "texto", "texto"
    elif any(x in ml for x in ["biolog","célula","celula"]):
        desc_esp, tipo_sug, lang_sug = config_nivel.get("biologia", config_nivel["descripcion"]), "texto", "texto"
    elif any(x in ml for x in ["quim","átomo","atomo"]):
        desc_esp, tipo_sug, lang_sug = config_nivel.get("quimica", config_nivel["descripcion"]), "texto", "texto"
    elif any(x in ml for x in ["fisic","fuerza","energi"]):
        desc_esp, tipo_sug, lang_sug = config_nivel.get("fisica", config_nivel["descripcion"]), "matematica", "matematica"
    elif any(x in ml for x in ["histor","guerra"]):
        desc_esp, tipo_sug, lang_sug = config_nivel.get("historia", config_nivel["descripcion"]), "texto", "texto"
    else:
        desc_esp, tipo_sug, lang_sug = config_nivel.get("general", config_nivel["descripcion"]), "texto", "texto"

    try:
        cliente = Groq(api_key=Config.GROQ_API_KEY)
        prompt  = f"""Eres tutor de {materia}. Crea UN ejercicio práctico NUEVO.
MATERIA: {materia} | NIVEL {nivel_num} — {config_nivel["nombre"]} | DIFICULTAD: {desc_esp}
INTERÉS: {interes} | TIPO: {tipo_sug}
{vistos_texto}
Conecta el ejercicio con el interés "{interes}". Es EXCLUSIVAMENTE de {materia}.
Responde SOLO en JSON:
{{"tipo":"{tipo_sug}","titulo":"Título breve","instruccion":"Instrucción clara","ejemplo_entrada":"","pista":"Pista sin revelar respuesta","pistas_extra":["paso1","paso2","paso3"],"respuesta_correcta":"Respuesta completa","explicacion":"Paso a paso","lenguaje":"{lang_sug}"}}"""

        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000, temperature=0.9)

        texto = respuesta.choices[0].message.content
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            ejercicio              = json.loads(match.group())
            titulo_ej              = ejercicio.get("titulo", "Ejercicio")
            hash_ej                = hashlib.md5(f"{titulo_ej}{materia}{nivel_num}".encode()).hexdigest()[:16]
            guardar_ejercicio_visto(usuario_id, materia, nivel_num, titulo_ej, hash_ej)
            ejercicio["nivel_num"] = nivel_num
            ejercicio["nivel_nombre"] = config_nivel["nombre"]
            ejercicio["interes"]   = interes
            return jsonify(ejercicio), 200
        return jsonify({"error": "No se pudo generar"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/evaluar_respuesta", methods=["POST"])
def evaluar_respuesta():
    datos             = request.json
    ejercicio         = datos.get("ejercicio", "")
    respuesta_usuario = datos.get("respuesta_usuario", "")
    tipo              = datos.get("tipo", "texto")
    materia           = datos.get("materia", "")
    try:
        cliente = Groq(api_key=Config.GROQ_API_KEY)
        prompt  = f"""Evalúa la respuesta del estudiante.
EJERCICIO: {ejercicio}
RESPUESTA: {respuesta_usuario}
TIPO: {tipo} | MATERIA: {materia}
Responde SOLO en JSON:
{{"correcto":true/false,"puntaje":0-100,"mensaje":"Mensaje motivador","errores":"Errores si hay","correccion":"Solución correcta","siguiente_paso":"Qué practicar ahora"}}"""
        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600, temperature=0.4)
        texto = respuesta.choices[0].message.content
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            return jsonify(json.loads(match.group())), 200
        return jsonify({"error": "No se pudo evaluar"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/ejecutar_codigo", methods=["POST"])
def ejecutar_codigo():
    datos    = request.json
    codigo   = datos.get("codigo", "")
    lenguaje = datos.get("lenguaje", "python")
    try:
        cliente = Groq(api_key=Config.GROQ_API_KEY)
        prompt  = f"""Simula la ejecución del código en {lenguaje} y muestra el output exacto.
```{lenguaje}
{codigo}
```
Responde SOLO en JSON:
{{"output":"Output exacto","error":"Error si hay","exitoso":true/false,"explicacion":"Qué hizo el código"}}"""
        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400, temperature=0.1)
        texto = respuesta.choices[0].message.content
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            return jsonify(json.loads(match.group())), 200
        return jsonify({"error": "No se pudo ejecutar"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/mis_sesiones", methods=["GET"])
def mis_sesiones():
    usuario_id = session.get("usuario_id", 1)
    filas = ejecutar_db("""SELECT sesion_id,titulo,materia,fecha,fecha_ultimo,total_mensajes
        FROM sesiones_chat WHERE usuario_id=%s ORDER BY fecha_ultimo DESC LIMIT 20""",
        (usuario_id,), fetchall=True)
    if not filas:
        return jsonify([]), 200
    return jsonify([{"sesion_id":f[0],"titulo":f[1] or "Conversación","materia":f[2] or "",
                     "fecha_inicio":str(f[3]),"fecha_ultimo":str(f[4]),"total_mensajes":f[5] or 0}
                    for f in filas]), 200


@chat_bp.route("/sesion/<sid>", methods=["GET"])
def ver_sesion(sid):
    usuario_id = session.get("usuario_id", 1)
    mensajes = ejecutar_db("""SELECT rol,mensaje,fecha FROM historial_chat
        WHERE usuario_id=%s AND sesion_id=%s ORDER BY fecha ASC""",
        (usuario_id, sid), fetchall=True)
    if not mensajes:
        return jsonify([]), 200
    return jsonify([{"rol":m[0],"mensaje":m[1],"fecha":str(m[2])} for m in mensajes]), 200


@chat_bp.route("/eliminar_sesion/<sesion_id>", methods=["DELETE"])
def eliminar_sesion(sesion_id):
    usuario_id = session.get("usuario_id", 1)
    ejecutar_db("DELETE FROM historial_chat WHERE sesion_id=%s AND usuario_id=%s", (sesion_id, usuario_id), commit=True)
    ejecutar_db("DELETE FROM sesiones_chat WHERE sesion_id=%s AND usuario_id=%s", (sesion_id, usuario_id), commit=True)
    return jsonify({"mensaje": "Sesión eliminada"}), 200


@chat_bp.route("/mi_rendimiento", methods=["GET"])
def mi_rendimiento():
    usuario_id = session.get("usuario_id", 1)
    try:
        con = get_db(); cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM sesiones_chat WHERE usuario_id=%s", (usuario_id,))
        total_sesiones = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM historial_chat WHERE usuario_id=%s AND rol='user'", (usuario_id,))
        total_mensajes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM planes_estudio WHERE usuario_id=%s", (usuario_id,))
        total_planes = cur.fetchone()[0]
        cur.execute("""SELECT materia, COUNT(*) as v FROM sesiones_chat
            WHERE usuario_id=%s AND materia!='' AND materia IS NOT NULL
            GROUP BY materia ORDER BY v DESC LIMIT 5""", (usuario_id,))
        materias = [{"materia": f[0], "veces": f[1]} for f in cur.fetchall()]
        cur.execute("SELECT tipo_aprendizaje, nombre FROM usuarios WHERE id=%s", (usuario_id,))
        fila   = cur.fetchone()
        tipo   = fila[0] if fila else "sin detectar"
        nombre = fila[1] if fila else "Estudiante"
        cur.execute("SELECT COUNT(*) FROM historial_chat WHERE usuario_id=%s AND rol='assistant'", (usuario_id,))
        total_ai = cur.fetchone()[0] or 1
        estilos_conteo = {}
        for estilo in ["VISUAL","AUDITIVO","LECTOR","KINESTÉSICO"]:
            cur.execute("SELECT COUNT(*) FROM historial_chat WHERE usuario_id=%s AND rol='assistant' AND mensaje LIKE %s",
                        (usuario_id, f"%[PERFIL: {estilo}]%"))
            conteo = cur.fetchone()[0]
            estilos_conteo[estilo] = round((conteo / total_ai) * 100) if total_ai > 0 else 0
        cur.close(); con.close()
        return jsonify({"nombre": nombre, "total_sesiones": total_sesiones,
                        "total_mensajes": total_mensajes, "total_planes": total_planes,
                        "materias": materias, "tipo_aprendizaje": tipo,
                        "estilos_porcentaje": estilos_conteo}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/mis_planes", methods=["GET"])
def mis_planes():
    usuario_id = session.get("usuario_id", 1)
    filas = ejecutar_db("SELECT id,materia,interes,fecha FROM planes_estudio WHERE usuario_id=%s ORDER BY fecha DESC LIMIT 10",
                        (usuario_id,), fetchall=True)
    if not filas:
        return jsonify([]), 200
    return jsonify([{"id":p[0],"materia":p[1],"interes":p[2],"fecha":str(p[3])} for p in filas]), 200


@chat_bp.route("/guardar_plan", methods=["POST"])
def guardar_plan():
    datos      = request.json
    usuario_id = session.get("usuario_id", 1)
    ejecutar_db("INSERT INTO planes_estudio (usuario_id,materia,interes,plan_completo) VALUES (%s,%s,%s,%s)",
                (usuario_id, datos.get("materia",""), datos.get("interes",""), datos.get("plan","")), commit=True)
    return jsonify({"mensaje": "Plan guardado"}), 201