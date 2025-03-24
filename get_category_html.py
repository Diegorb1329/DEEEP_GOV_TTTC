import os
import json
import requests
from bs4 import BeautifulSoup
import time
import logging
from urllib.parse import urlparse, urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/category_download.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

def ensure_directory(directory):
    """Asegura que el directorio exista, lo crea si no existe."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Creado directorio: {directory}")

def sanitize_filename(name):
    """Convierte el nombre de categoría en un nombre de archivo válido."""
    return "".join(c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in name).strip()

def load_categories():
    """Carga las categorías desde el archivo JSON de categorías."""
    try:
        with open('gitcoin_categories_topics.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except FileNotFoundError:
        logger.error("Archivo gitcoin_categories_topics.json no encontrado.")
        try:
            # Intentar con el otro archivo JSON
            with open('final_grants_lab_content.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Filtrar solo elementos con clave 'category'
                return [item for item in data if 'category' in item]
        except FileNotFoundError:
            logger.error("Archivo final_grants_lab_content.json no encontrado.")
            return []

def setup_selenium_driver():
    """Configura y devuelve un driver de Selenium con Chrome en modo headless."""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Ejecutar en modo headless (sin interfaz gráfica)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        
        # Evitar que se muestre el mensaje "Chrome está siendo controlado por software automatizado"
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Error al configurar Selenium: {str(e)}")
        return None

def scroll_to_bottom(driver, wait_time=2, max_scrolls=50):
    """
    Hace scroll hasta el final de la página para cargar todo el contenido.
    
    Args:
        driver: Driver de Selenium.
        wait_time: Tiempo de espera entre scrolls (segundos).
        max_scrolls: Número máximo de scrolls para evitar bucles infinitos.
    """
    # Obtener altura inicial
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    # Contador de scrolls sin cambios de altura
    no_change_count = 0
    scroll_count = 0
    
    while scroll_count < max_scrolls:
        # Hacer scroll hasta el final
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Esperar a que se cargue el nuevo contenido
        time.sleep(wait_time)
        
        # Calcular nueva altura
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        # Si no hay cambio de altura, incrementar contador
        if new_height == last_height:
            no_change_count += 1
            if no_change_count >= 3:  # Después de 3 intentos sin cambios, asumimos que llegamos al final
                logger.info("Fin de la página alcanzado (altura no cambió)")
                break
        else:
            no_change_count = 0  # Resetear contador si la altura cambió
            
        last_height = new_height
        scroll_count += 1
        
        # Mostrar progreso de scroll
        logger.info(f"Scroll {scroll_count}/{max_scrolls} - Altura: {new_height}px")
    
    logger.info(f"Completados {scroll_count} scrolls")

def find_next_page_link(driver):
    """
    Encuentra el enlace para ir a la siguiente página si existe.
    
    Args:
        driver: Driver de Selenium.
        
    Returns:
        El enlace a la siguiente página o None si no se encuentra.
    """
    try:
        # Buscar enlaces de paginación
        next_links = driver.find_elements(By.CSS_SELECTOR, "div.pagination a.btn.btn-icon.btn-flat.btn-default.next")
        
        if next_links and len(next_links) > 0:
            next_link = next_links[0]
            # Verificar si el enlace está activo (no está deshabilitado)
            if not ("disabled" in next_link.get_attribute("class").split()):
                href = next_link.get_attribute("href")
                logger.info(f"Encontrado enlace a la siguiente página: {href}")
                return href
    except Exception as e:
        logger.warning(f"Error al buscar enlace de paginación: {str(e)}")
    
    return None

def get_page_number_from_url(url):
    """
    Extrae el número de página de la URL.
    
    Args:
        url: URL con posible parámetro de página.
        
    Returns:
        El número de página o 1 si no se encuentra.
    """
    try:
        if '?page=' in url:
            page = int(url.split('?page=')[1].split('&')[0])
            return page
        elif '/page/' in url:
            page = int(url.split('/page/')[1].split('/')[0])
            return page
    except Exception:
        pass
    
    return 1

def combine_html_files(file_list, output_file):
    """
    Combina múltiples archivos HTML en uno solo.
    
    Args:
        file_list: Lista de archivos HTML a combinar.
        output_file: Ruta del archivo de salida.
        
    Returns:
        True si la combinación fue exitosa, False en caso contrario.
    """
    try:
        if not file_list:
            return False
            
        # Extraer el contenido principal de cada archivo
        combined_content = []
        head_content = None
        
        for i, file_path in enumerate(file_list):
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Para el primer archivo, extraer la estructura básica
            if i == 0:
                head_content = str(soup.head)
                
                # Encontrar el contenedor principal donde están los temas
                main_container = soup.select_one("table.topic-list") or soup.select_one("div.topic-list")
                
                if main_container:
                    # Para el primer archivo guardamos la estructura
                    main_container_html = str(main_container)
                    combined_content.append(main_container_html)
            else:
                # Para los siguientes archivos, extraer solo los temas
                topics = soup.select("tr.topic-list-item") or soup.select("div.topic-list-item")
                
                if topics:
                    for topic in topics:
                        combined_content.append(str(topic))
        
        # Crear el HTML combinado
        combined_html = f"""
        <!DOCTYPE html>
        <html>
        {head_content}
        <body>
            <div id="main-content">
                {"".join(combined_content)}
            </div>
        </body>
        </html>
        """
        
        # Guardar el archivo combinado
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(combined_html)
            
        logger.info(f"Archivos HTML combinados en: {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error al combinar archivos HTML: {str(e)}")
        return False

def download_category_with_pagination(category_url, output_dir, category_name, max_pages=20):
    """
    Descarga todas las páginas de una categoría, haciendo scroll en cada una.
    
    Args:
        category_url: URL de la categoría.
        output_dir: Directorio donde guardar los archivos HTML.
        category_name: Nombre de la categoría.
        max_pages: Número máximo de páginas a descargar.
        
    Returns:
        Ruta del archivo HTML combinado o None si hubo un error.
    """
    try:
        logger.info(f"Iniciando descarga con paginación para categoría: {category_name}")
        
        temp_dir = os.path.join(output_dir, "temp")
        ensure_directory(temp_dir)
        
        # Crear nombre de archivo sanitizado
        filename = sanitize_filename(category_name)
        final_output_file = os.path.join(output_dir, f"{filename}.html")
        
        current_url = category_url
        current_page = 1
        temp_files = []
        
        driver = setup_selenium_driver()
        if not driver:
            logger.error("No se pudo inicializar el driver de Selenium")
            return None
        
        try:
            while current_page <= max_pages:
                logger.info(f"Procesando página {current_page} de la categoría '{category_name}'")
                
                # Navegar a la URL de la página actual
                driver.get(current_url)
                
                # Esperar a que se cargue el contenido principal
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table.topic-list tbody tr, div.topic-list-item"))
                    )
                except TimeoutException:
                    logger.warning(f"Tiempo de espera agotado esperando elementos en {current_url}, continuando de todos modos")
                
                # Hacer scroll hasta el final de la página
                scroll_to_bottom(driver)
                
                # Guardar el HTML de la página actual
                page_html = driver.page_source
                temp_file = os.path.join(temp_dir, f"{filename}_page{current_page}.html")
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(page_html)
                
                temp_files.append(temp_file)
                logger.info(f"Guardada página {current_page} en: {temp_file}")
                
                # Buscar enlace a la siguiente página
                next_page_link = find_next_page_link(driver)
                
                if not next_page_link:
                    logger.info(f"No hay más páginas para la categoría '{category_name}'")
                    break
                
                # Actualizar URL y contador de página
                current_url = next_page_link
                current_page += 1
                
                # Esperar antes de cargar la siguiente página
                time.sleep(2)
            
            # Combinar todos los archivos temporales en uno solo
            if temp_files:
                combine_html_files(temp_files, final_output_file)
                logger.info(f"HTML completo (todas las páginas) guardado en: {final_output_file}")
                return final_output_file
            else:
                logger.warning(f"No se encontraron páginas para la categoría '{category_name}'")
                return None
            
        finally:
            # Cerrar el driver de Selenium
            driver.quit()
            
    except Exception as e:
        logger.error(f"Error al descargar categoría con paginación: {str(e)}")
        return None

def download_all_categories():
    """Descarga el HTML para todas las categorías."""
    # Crear directorios para guardar los archivos
    output_dir = "categories_html"
    ensure_directory(output_dir)
    ensure_directory("logs")
    
    # Cargar categorías desde el archivo JSON
    categories_data = load_categories()
    
    if not categories_data:
        logger.error("No se encontraron datos de categorías para procesar.")
        return
    
    logger.info(f"Encontradas {len(categories_data)} categorías para procesar.")
    
    # Procesar cada categoría
    for item in categories_data:
        category = item.get('category', {})
        category_name = category.get('name')
        category_url = category.get('url')
        
        if not category_name or not category_url:
            logger.warning(f"Categoría sin nombre o URL: {category}")
            continue
        
        # Descargar la categoría con manejo de paginación
        output_file = download_category_with_pagination(category_url, output_dir, category_name)
        
        # Esperar un tiempo entre solicitudes para evitar sobrecarga
        time.sleep(2)
    
    logger.info("Proceso completado.")

def download_categories_from_html():
    """Extrae categorías directamente del HTML de la página principal y descarga su contenido."""
    output_dir = "categories_html"
    ensure_directory(output_dir)
    ensure_directory("logs")
    
    try:
        # Primero descargar la página principal con Selenium para obtener todas las categorías
        logger.info("Descargando página principal de categorías con Selenium")
        
        driver = setup_selenium_driver()
        if not driver:
            logger.error("No se pudo inicializar el driver de Selenium")
            return
            
        try:
            # Navegar a la URL principal de categorías
            driver.get("https://gov.gitcoin.co/categories")
            
            # Esperar a que se carguen las categorías
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.category-list tbody tr"))
                )
            except TimeoutException:
                logger.warning("Tiempo de espera agotado esperando categorías, continuando de todos modos")
            
            # Guardar la página principal para referencia
            content = driver.page_source
            with open('categories_full.html', 'w', encoding='utf-8') as f:
                f.write(content)
                
            # Procesar el HTML con BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            # Encontrar todas las filas de la tabla de categorías
            rows = soup.select("table.category-list tbody tr")
            logger.info(f"Encontradas {len(rows)} categorías en el HTML.")
            
            for row in rows:
                # Extraer información de la categoría
                category_td = row.select_one("td.category")
                
                if not category_td:
                    continue
                    
                # Extraer nombre y enlace
                category_name_elem = category_td.select_one("h3 a span")
                category_link_elem = category_td.select_one("h3 a")
                
                if not category_name_elem or not category_link_elem:
                    continue
                    
                category_name = category_name_elem.text.strip()
                category_url = category_link_elem.get('href')
                
                if not category_url:
                    continue
                    
                # Convertir a URL completa si es relativa
                if category_url.startswith('/'):
                    category_url = f"https://gov.gitcoin.co{category_url}"
                
                # Descargar la categoría con manejo de paginación
                output_file = download_category_with_pagination(category_url, output_dir, category_name)
                
                # Esperar un tiempo entre solicitudes para evitar sobrecarga
                time.sleep(2)
            
        finally:
            # Cerrar el driver de Selenium
            driver.quit()
            
        logger.info("Descarga desde HTML completada.")
        
    except Exception as e:
        logger.error(f"Error al procesar categorías: {str(e)}")

if __name__ == "__main__":
    # Ejecutar ambos métodos para asegurar la descarga de todas las categorías
    logger.info("Iniciando descarga de categorías desde archivos JSON...")
    download_all_categories()
    
    logger.info("Iniciando descarga de categorías desde HTML...")
    download_categories_from_html()
    
    logger.info("Proceso completo.") 