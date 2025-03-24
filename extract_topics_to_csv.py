import os
import csv
from bs4 import BeautifulSoup
import logging
import re
import argparse
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/extract_topics.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

def ensure_directory(directory):
    """Asegura que el directorio exista, lo crea si no existe."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Creado directorio: {directory}")

def get_category_name_from_file(filename):
    """Extrae el nombre de la categoría del nombre del archivo."""
    # Quitar la extensión .html
    name = os.path.splitext(filename)[0]
    # Reemplazar caracteres especiales (_, etc.) por espacios cuando sea apropiado
    name = name.replace('_', ' ').strip()
    return name

def extract_topics_from_html(html_file, category_name):
    """Extrae los temas y sus enlaces de un archivo HTML de categoría."""
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Buscar todos los elementos que contienen temas
        # Hay dos patrones comunes: tr.topic-list-item o div.topic-list-item
        topics = soup.select("tr.topic-list-item") or soup.select("div.topic-list-item") or soup.select("tbody tr")
        
        logger.info(f"Encontrados {len(topics)} temas en la categoría '{category_name}'")
        
        results = []
        for topic in topics:
            # Buscar el título y el enlace del tema
            # Diferentes estructuras HTML posibles
            title_link = topic.select_one("a.title") or topic.select_one("span.link-top-line a") or topic.select_one("td.main-link a")
            
            if title_link:
                title = title_link.get_text(strip=True)
                url = title_link.get('href')
                
                # Asegurarse de que la URL sea absoluta
                if url and url.startswith('/'):
                    url = f"https://gov.gitcoin.co{url}"
                
                # Intentar extraer más información si está disponible
                author = None
                author_link = None
                date = None
                replies = None
                views = None
                
                # Intentar obtener autor
                author_elem = topic.select_one("a.creator span") or topic.select_one("td.posters a")
                if author_elem:
                    author = author_elem.get_text(strip=True)
                
                # Intentar obtener enlace del autor
                author_link_elem = topic.select_one("a.creator") or topic.select_one("td.posters a")
                if author_link_elem:
                    author_link = author_link_elem.get('href')
                    if author_link and author_link.startswith('/'):
                        author_link = f"https://gov.gitcoin.co{author_link}"
                
                # Intentar obtener fecha
                date_elem = topic.select_one("td.activity a span") or topic.select_one("time.post-time") or topic.select_one("td.activity")
                if date_elem:
                    date = date_elem.get_text(strip=True)
                
                # Intentar obtener número de respuestas
                replies_elem = topic.select_one("td.num.posts")
                if replies_elem:
                    replies = replies_elem.get_text(strip=True)
                
                # Intentar obtener vistas
                views_elem = topic.select_one("td.num.views")
                if views_elem:
                    views = views_elem.get_text(strip=True)
                
                if title and url:
                    topic_data = {
                        'category': category_name,
                        'title': title,
                        'url': url
                    }
                    
                    # Agregar información adicional si está disponible
                    if author:
                        topic_data['author'] = author
                    if author_link:
                        topic_data['author_link'] = author_link
                    if date:
                        topic_data['date'] = date
                    if replies:
                        topic_data['replies'] = replies
                    if views:
                        topic_data['views'] = views
                    
                    results.append(topic_data)
        
        return results
    
    except Exception as e:
        logger.error(f"Error al procesar {html_file}: {str(e)}")
        return []

def scan_categories_directory(directory, filter_category=None):
    """Escanea el directorio de categorías y extrae los temas de cada archivo HTML."""
    all_topics = []
    
    # Verificar que el directorio existe
    if not os.path.exists(directory):
        logger.error(f"El directorio {directory} no existe")
        return all_topics
    
    # Obtener todos los archivos HTML en el directorio
    html_files = [f for f in os.listdir(directory) if f.endswith('.html')]
    logger.info(f"Encontrados {len(html_files)} archivos HTML en {directory}")
    
    # Procesar cada archivo HTML
    for filename in html_files:
        file_path = os.path.join(directory, filename)
        category_name = get_category_name_from_file(filename)
        
        # Si hay un filtro de categoría y no coincide, saltamos este archivo
        if filter_category and filter_category.lower() not in category_name.lower():
            logger.info(f"Omitiendo categoría: {category_name} (no coincide con el filtro)")
            continue
        
        logger.info(f"Procesando categoría: {category_name}")
        topics = extract_topics_from_html(file_path, category_name)
        all_topics.extend(topics)
    
    return all_topics

def export_to_csv(topics, output_file):
    """Exporta los temas a un archivo CSV."""
    try:
        if not topics:
            logger.warning("No hay temas para exportar")
            return False
            
        # Determinar las columnas basadas en las claves disponibles en el primer tema
        fieldnames = list(topics[0].keys())
        
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

def parse_arguments():
    """Parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description='Extrae temas de categorías de Gitcoin y los exporta a CSV.')
    parser.add_argument('--category', '-c', type=str, help='Filtra por categoría (parcial)')
    parser.add_argument('--output', '-o', type=str, default='topics_by_category.csv', help='Archivo CSV de salida')
    parser.add_argument('--input-dir', '-i', type=str, default='categories_html', help='Directorio con los archivos HTML')
    
    return parser.parse_args()

def main():
    # Parsear argumentos
    args = parse_arguments()
    
    # Configurar directorios y archivos
    categories_dir = args.input_dir
    output_file = args.output
    filter_category = args.category
    
    ensure_directory("logs")
    
    if filter_category:
        logger.info(f"Iniciando extracción de temas con filtro de categoría: '{filter_category}'")
    else:
        logger.info("Iniciando extracción de temas de todas las categorías...")
    
    # Escanear directorio de categorías
    all_topics = scan_categories_directory(categories_dir, filter_category)
    
    logger.info(f"Total de temas encontrados: {len(all_topics)}")
    
    # Exportar a CSV
    if all_topics:
        export_to_csv(all_topics, output_file)
        logger.info(f"Proceso completado. Se ha creado el archivo {output_file}")
    else:
        logger.warning("No se encontraron temas para exportar")

if __name__ == "__main__":
    main() 