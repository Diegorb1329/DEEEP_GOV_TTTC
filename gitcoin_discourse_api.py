import os
import json
import csv
import requests
import time
import logging
from urllib.parse import urljoin
from collections import Counter

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/discourse_api.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Asegurar que el directorio de logs exista
if not os.path.exists("logs"):
    os.makedirs("logs")

def ensure_directory(directory):
    """Asegura que el directorio exista, lo crea si no existe."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Creado directorio: {directory}")

def format_date(raw_date):
    """Formatea la fecha en un formato más legible como 'Feb '22'."""
    # Las fechas de la API vienen en formato ISO: "2022-02-15T12:34:56.789Z"
    if not raw_date:
        return ""
    
    try:
        if 'T' in raw_date:
            from datetime import datetime
            
            # Convertir de ISO a objeto datetime
            date_obj = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            
            # Obtener mes abreviado y año
            month_abbr = date_obj.strftime('%b')
            year = date_obj.strftime('%y')
            
            # Formato final: "Feb '22"
            return f"{month_abbr} '{year}"
        else:
            # Si ya viene con un formato adecuado (como "Feb '22")
            return raw_date
    except Exception as e:
        logger.warning(f"Error al formatear fecha {raw_date}: {str(e)}")
        # Si hay error, devolver la fecha en formato YYYY-MM-DD
        if raw_date and 'T' in raw_date:
            return raw_date.split('T')[0]
        return raw_date

def format_number(number):
    """Formatea números grandes para mejorar legibilidad."""
    if isinstance(number, int):
        if number >= 1000:
            return f"{number/1000:.1f}k"
        return str(number)
    return number

def get_category_topics(category_id, category_slug, page=1):
    """
    Obtiene los temas de una categoría usando la API JSON de Discourse.
    
    Args:
        category_id: ID de la categoría
        category_slug: Slug de la categoría
        page: Número de página
        
    Returns:
        Lista de temas encontrados
    """
    base_url = "https://gov.gitcoin.co"
    url = f"{base_url}/c/{category_slug}/{category_id}/l/latest.json?filter=default&page={page}"
    
    logger.info(f"Solicitando página {page} de categoría {category_slug} (ID: {category_id})")
    
    try:
        # Añadir user-agent y otros encabezados para evitar ser bloqueado
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "es-US,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"{base_url}/c/{category_slug}/{category_id}",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Lanzar excepción si el status code no es 200
        
        # Parsear la respuesta JSON
        data = response.json()
        
        # Verificar si hay error o si falta la estructura esperada
        if "errors" in data:
            logger.error(f"Error en la respuesta: {data['errors']}")
            return None, False
            
        # Extraer la lista de temas
        topic_list = data.get("topic_list", {})
        topics = topic_list.get("topics", [])
        
        logger.info(f"Obtenidos {len(topics)} temas de la página {page}")
        
        # Determinar si hay más páginas
        more_topics_url = topic_list.get("more_topics_url")
        topics_left = topic_list.get("per_page_count", 0)
        
        # CORRECCIÓN: verificar de manera más confiable si hay más páginas
        # 1. Si hay URL para más temas, definitivamente hay más
        has_more_from_url = bool(more_topics_url)
        
        # 2. Si hay exactamente el número máximo de temas por página (30), probablemente hay más
        # incluso si el servidor no indica explícitamente que hay más
        items_per_page = 30  # Discourse generalmente usa 30 ítems por página
        has_more_from_count = len(topics) >= items_per_page
        
        # 3. Si hay temas pendientes según el conteo, hay más
        has_more_from_left = topics_left > 0
        
        # Combinamos todas las condiciones para decidir si hay más páginas
        has_more = has_more_from_url or (has_more_from_count and page < 20)  # Limitamos a 20 páginas por seguridad
        
        logger.info(f"¿Hay más páginas? {has_more} (URL: {has_more_from_url}, Count: {has_more_from_count}, Left: {has_more_from_left})")
        
        return topics, has_more
        
    except requests.RequestException as e:
        logger.error(f"Error al hacer la solicitud HTTP: {str(e)}")
        return None, False
    except json.JSONDecodeError as e:
        logger.error(f"Error al decodificar JSON: {str(e)}")
        return None, False
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        return None, False

def get_all_category_topics(category_id, category_slug, category_name, max_pages=20):
    """
    Obtiene todos los temas de una categoría paginando por todas las páginas disponibles.
    
    Args:
        category_id: ID de la categoría
        category_slug: Slug de la categoría
        category_name: Nombre legible de la categoría
        max_pages: Número máximo de páginas a descargar
        
    Returns:
        Lista de temas procesados con la información requerida
    """
    all_topics = []
    current_page = 1
    has_more = True
    base_url = "https://gov.gitcoin.co"
    
    # Contador para verificar si estamos obteniendo nuevos temas en cada solicitud
    last_total_topics = 0
    empty_pages_count = 0
    
    while (has_more or current_page == 1) and current_page <= max_pages:
        topics, has_more = get_category_topics(category_id, category_slug, current_page)
        
        if topics is None:
            logger.error(f"Error al obtener la página {current_page} de la categoría {category_name}")
            break
        
        # Verificar si obtuvimos temas nuevos
        if len(topics) == 0:
            empty_pages_count += 1
            if empty_pages_count >= 2:  # Si dos páginas seguidas están vacías, terminamos
                logger.warning(f"Se encontraron {empty_pages_count} páginas vacías consecutivas. Terminando la extracción.")
                break
        else:
            empty_pages_count = 0  # Resetear el contador de páginas vacías
        
        # Conteo de temas acumulados
        previous_count = len(all_topics)
            
        # Procesar los temas
        for topic in topics:
            # Filtrar solo temas regulares (excluir temas fijados, cerrados, etc. si es necesario)
            # Extraer la información relevante para cada tema
            
            # Url del tema
            topic_id = topic.get("id")
            slug = topic.get("slug", "")
            url = f"{base_url}/t/{slug}/{topic_id}"
            
            # Título del tema
            title = topic.get("title", "")
            
            # Información del autor
            posters = topic.get("posters", [])
            author_info = next((p for p in posters if p.get("description") == "Original Poster"), None)
            author_username = None
            
            # Obtener username del autor - varios intentos
            # 1. Revisar si hay un username directo en los usuarios participantes
            if topic.get("participants"):
                for participant in topic.get("participants", []):
                    # Si encontramos el usuario original poster, usamos su nombre
                    if author_info and participant.get("id") == author_info.get("user_id"):
                        author_username = participant.get("username")
                        break
            
            # 2. Intentar obtener desde el creador si existe
            if not author_username and "creator" in topic and isinstance(topic["creator"], dict):
                author_username = topic["creator"].get("username")
            
            # 3. Intentar obtener desde el primer poster
            if not author_username and "posters" in topic and len(topic["posters"]) > 0:
                first_poster_id = topic["posters"][0].get("user_id")
                for user in topic.get("participants", []):
                    if user.get("id") == first_poster_id:
                        author_username = user.get("username")
                        break
            
            # Generar el enlace del autor
            if author_username:
                author_link = f"{base_url}/u/{author_username}"
            else:
                # Si no podemos obtener el username, usar user_id o creator_user_id
                user_id = None
                if author_info:
                    user_id = author_info.get("user_id")
                if not user_id:
                    user_id = topic.get("creator_user_id", "unknown")
                author_link = f"{base_url}/u/user-{user_id}"
            
            # Fecha - intentar obtener la fecha más relevante
            date = None
            
            # 1. Intentar obtener last_posted_at (última actividad)
            last_posted_at = topic.get("last_posted_at")
            if last_posted_at:
                date = last_posted_at
            
            # 2. Si no hay última actividad, usar bumped_at (fecha de promoción)
            if not date:
                bumped_at = topic.get("bumped_at")
                if bumped_at:
                    date = bumped_at
            
            # 3. Si aún no hay fecha, usar created_at (fecha de creación)
            if not date:
                created_at = topic.get("created_at")
                if created_at:
                    date = created_at
            
            # Formatear fecha de manera más legible
            date_formatted = format_date(date) if date else ""
            
            # Respuestas y vistas
            replies = topic.get("reply_count", 0)
            views = topic.get("views", 0)
            
            # Formatear números grandes
            replies_formatted = format_number(replies)
            views_formatted = format_number(views)
            
            # Crear diccionario con la información del tema
            topic_data = {
                "category": category_name,
                "title": title,
                "url": url,
                "author_link": author_link,
                "date": date_formatted,
                "replies": replies_formatted,
                "views": views_formatted
            }
            
            all_topics.append(topic_data)
        
        # Verificar si obtuvimos nuevos temas en esta solicitud
        new_topics_count = len(all_topics) - previous_count
        logger.info(f"Añadidos {new_topics_count} nuevos temas de la página {current_page}")
        
        # Si no obtuvimos nuevos temas diferentes a los anteriores, salimos del bucle
        if new_topics_count == 0 and current_page > 1:
            logger.warning(f"No se obtuvieron nuevos temas en la página {current_page}. Terminando extracción.")
            break
        
        # Verificación adicional: si llegamos a la página max_pages y todavía hay más, advertir
        if current_page == max_pages and has_more:
            logger.warning(f"Se alcanzó el límite de {max_pages} páginas, pero aún hay más temas. Considere aumentar max_pages.")
        
        # Pausa entre solicitudes para no sobrecargar el servidor
        if has_more:
            logger.info(f"Esperando 1 segundo antes de solicitar la siguiente página...")
            time.sleep(1)
            current_page += 1
    
    logger.info(f"Total de temas encontrados en la categoría {category_name}: {len(all_topics)}")
    return all_topics

def get_categories():
    """
    Obtiene la lista de categorías disponibles en el foro.
    
    Returns:
        Lista de categorías con su ID, slug y nombre
    """
    base_url = "https://gov.gitcoin.co"
    url = f"{base_url}/categories.json"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        category_list = data.get("category_list", {})
        categories = category_list.get("categories", [])
        
        result = []
        for category in categories:
            # Solo añadir categorías regulares, ignorar categorías especiales
            if not category.get("read_restricted", False):
                category_data = {
                    "id": category.get("id"),
                    "slug": category.get("slug"),
                    "name": category.get("name")
                }
                result.append(category_data)
        
        return result
        
    except Exception as e:
        logger.error(f"Error al obtener la lista de categorías: {str(e)}")
        return []

def export_to_csv(topics, output_file):
    """Exporta los temas a un archivo CSV."""
    try:
        if not topics:
            logger.warning("No hay temas para exportar")
            return False
            
        # Determinar las columnas basadas en las claves disponibles en el primer tema
        fieldnames = ["category", "title", "url", "author_link", "date", "replies", "views"]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for topic in topics:
                writer.writerow(topic)
        
        logger.info(f"Archivo CSV guardado en: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error al guardar CSV: {str(e)}")
        return False

def print_category_stats(topics):
    """Imprime estadísticas sobre la cantidad de temas por categoría."""
    # Contar temas por categoría
    category_counts = Counter([topic["category"] for topic in topics])
    
    # Ordenar categorías por cantidad de temas (de mayor a menor)
    sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    
    print("\n===== ESTADÍSTICAS DE TEMAS POR CATEGORÍA =====")
    print(f"Total de temas: {len(topics)}")
    print("Distribución por categoría:")
    
    for category, count in sorted_categories:
        percentage = (count / len(topics)) * 100
        print(f"  - {category}: {count} temas ({percentage:.1f}%)")
    
    print("===============================================\n")

def main():
    output_file = "topics_by_category.csv"
    max_pages_per_category = 20  # Ajustar según sea necesario
    
    logger.info("Iniciando extracción de temas desde la API de Discourse...")
    
    # Obtener lista de categorías
    categories = get_categories()
    
    if not categories:
        # Si falla la obtención automática, usar categorías predefinidas con IDs precisos
        logger.warning("No se pudieron obtener categorías automáticamente. Usando categorías predefinidas.")
        categories = [
            {"id": 6, "slug": "governancevision", "name": "Governance & Vision"},
            {"id": 7, "slug": "publicgoods", "name": "Public Goods"},
            {"id": 8, "slug": "proposals", "name": "Proposals"},
            {"id": 9, "slug": "metagovdao", "name": "MetaGovDAO"},
            {"id": 10, "slug": "grants", "name": "Gitcoin Grants"},
            {"id": 11, "slug": "citizengrants", "name": "Citizen Grants"},
            {"id": 12, "slug": "grantslab", "name": "Grants Lab"},
            {"id": 13, "slug": "partnerships", "name": "Partnerships"},
            {"id": 14, "slug": "ideas", "name": "Ideas and Discussion"},
            {"id": 15, "slug": "pgn", "name": "PGN"},
            {"id": 16, "slug": "communityspotlight", "name": "Community Spotlight"},
            {"id": 17, "slug": "news", "name": "News and Community"}
        ]
    else:
        # Categorías que sabemos que deberían existir y sus IDs conocidos
        known_categories = {
            "governancevision": {"id": 6, "name": "Governance & Vision"},
            "publicgoods": {"id": 7, "name": "Public Goods"},
            "proposals": {"id": 8, "name": "Proposals"},
            "metagovdao": {"id": 9, "name": "MetaGovDAO"},
            "grants": {"id": 10, "name": "Gitcoin Grants"},
            "citizengrants": {"id": 11, "name": "Citizen Grants"},
            "grantslab": {"id": 12, "name": "Grants Lab"},
            "partnerships": {"id": 13, "name": "Partnerships"},
            "ideas": {"id": 14, "name": "Ideas and Discussion"},
            "pgn": {"id": 15, "name": "PGN"},
            "communityspotlight": {"id": 16, "name": "Community Spotlight"},
            "news": {"id": 17, "name": "News and Community"}
        }
        
        # Verificar y corregir las categorías
        corrected_categories = []
        existing_slugs = {c["slug"]: c for c in categories}
        
        # Asegurarnos de que tenemos todas las categorías con sus IDs correctos
        for slug, info in known_categories.items():
            if slug in existing_slugs:
                # Si la categoría existe en la lista obtenida, usar esa pero verificar el ID
                category = existing_slugs[slug]
                if category["id"] != info["id"]:
                    logger.warning(f"ID incorrecto para {slug}: {category['id']} (debería ser {info['id']}). Corrigiendo.")
                    category["id"] = info["id"]
                corrected_categories.append(category)
            else:
                # Si la categoría no existe en la lista obtenida, añadirla
                logger.info(f"Añadiendo categoría faltante: {slug} (ID: {info['id']})")
                corrected_categories.append({
                    "id": info["id"],
                    "slug": slug,
                    "name": info["name"]
                })
        
        # Verificar categorías adicionales que se obtuvieron pero no están en nuestra lista conocida
        for slug, category in existing_slugs.items():
            if slug not in known_categories:
                logger.info(f"Añadiendo categoría adicional descubierta: {slug} (ID: {category['id']})")
                corrected_categories.append(category)
        
        # Usar la lista corregida
        categories = corrected_categories
    
    logger.info(f"Total de categorías a procesar: {len(categories)}")
    
    # Ordenar categorías por ID para procesarlas en un orden consistente
    categories.sort(key=lambda x: x["id"])
    
    # Obtener temas de todas las categorías
    all_topics = []
    
    for category in categories:
        category_id = category["id"]
        category_slug = category["slug"]
        category_name = category["name"]
        
        logger.info(f"Procesando categoría: {category_name} (ID: {category_id}, Slug: {category_slug})")
        
        category_topics = get_all_category_topics(
            category_id, 
            category_slug, 
            category_name,
            max_pages=max_pages_per_category
        )
        
        all_topics.extend(category_topics)
        
        # Pausa entre categorías para no sobrecargar el servidor
        if category != categories[-1]:  # Si no es la última categoría
            logger.info("Esperando 1 segundo antes de procesar la siguiente categoría...")
            time.sleep(1)
    
    # Exportar todos los temas a CSV
    if all_topics:
        export_to_csv(all_topics, output_file)
        
        # Imprimir estadísticas
        print_category_stats(all_topics)
        
        logger.info(f"Proceso completado. Total de temas extraídos: {len(all_topics)}")
    else:
        logger.error("No se encontraron temas para exportar")

if __name__ == "__main__":
    main() 