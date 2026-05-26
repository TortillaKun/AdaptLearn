from flask import Blueprint, request, jsonify
import requests

fuentes_bp = Blueprint('fuentes', __name__)

# ── OPENALEX (gratis, sin key) ─────────────────────
def buscar_openalex(tema, limite=3):
    try:
        url = f"https://api.openalex.org/works"
        params = {
            'search': tema,
            'per_page': limite,
            'filter': 'language:es|en',
            'sort': 'cited_by_count:desc'
        }
        res  = requests.get(url, params=params, timeout=5)
        data = res.json()
        resultados = []
        for item in data.get('results', []):
            titulo = item.get('title', 'Sin título')
            autores = ', '.join([
                a.get('author', {}).get('display_name', '')
                for a in item.get('authorships', [])[:2]
            ])
            link = item.get('primary_location', {}).get('landing_page_url') or \
                   f"https://openalex.org/{item.get('id','').split('/')[-1]}"
            anio = item.get('publication_year', '')
            resultados.append({
                'titulo':  titulo,
                'autores': autores or 'Autores desconocidos',
                'link':    link,
                'anio':    anio,
                'fuente':  'OpenAlex'
            })
        return resultados
    except:
        return []

# ── SEMANTIC SCHOLAR (gratis, sin key) ────────────
def buscar_semantic(tema, limite=3):
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            'query':  tema,
            'limit':  limite,
            'fields': 'title,authors,year,externalIds,openAccessPdf'
        }
        res  = requests.get(url, params=params, timeout=5)
        data = res.json()
        resultados = []
        for item in data.get('data', []):
            titulo  = item.get('title', 'Sin título')
            autores = ', '.join([
                a.get('name', '') for a in item.get('authors', [])[:2]
            ])
            pdf  = item.get('openAccessPdf', {})
            link = pdf.get('url') if pdf else None
            if not link:
                doi = item.get('externalIds', {}).get('DOI')
                link = f"https://doi.org/{doi}" if doi else 'https://www.semanticscholar.org'
            resultados.append({
                'titulo':  titulo,
                'autores': autores or 'Autores desconocidos',
                'link':    link,
                'anio':    item.get('year', ''),
                'fuente':  'Semantic Scholar'
            })
        return resultados
    except:
        return []

# ── ENDPOINT PRINCIPAL ─────────────────────────────
@fuentes_bp.route('/buscar_fuentes', methods=['POST'])
def buscar_fuentes():
    datos = request.json
    tema  = datos.get('tema', '')

    if not tema:
        return jsonify({'error': 'Tema requerido'}), 400

    # Buscar en ambas fuentes simultáneamente
    resultados_openalex  = buscar_openalex(tema)
    resultados_semantic  = buscar_semantic(tema)

    # Combinar resultados
    todos = resultados_openalex + resultados_semantic

    return jsonify({
        'tema':      tema,
        'total':     len(todos),
        'fuentes':   todos
    }), 200