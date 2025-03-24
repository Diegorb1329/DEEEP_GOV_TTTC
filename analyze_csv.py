import csv
import sys
from collections import Counter
import matplotlib.pyplot as plt
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

def read_csv(file_path):
    """Lee un archivo CSV y devuelve una lista de diccionarios con los temas."""
    try:
        topics = []
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                topics.append(row)
        
        logger.info(f"Se han leído {len(topics)} temas del archivo {file_path}")
        return topics
    except Exception as e:
        logger.error(f"Error al leer el archivo CSV: {str(e)}")
        return []

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
    
    return sorted_categories

def generate_pie_chart(categories_data, output_file=None):
    """Genera un gráfico de pastel con la distribución de temas por categoría."""
    try:
        # Extraer nombres y cantidades
        names = [cat[0] for cat in categories_data]
        values = [cat[1] for cat in categories_data]
        
        # Limitar a las 10 principales categorías si hay más
        if len(names) > 10:
            others_sum = sum(values[9:])
            names = names[:9] + ["Otros"]
            values = values[:9] + [others_sum]
        
        # Crear figura y ejes
        plt.figure(figsize=(12, 8))
        
        # Generar gráfico de pastel
        plt.pie(
            values, 
            labels=names,
            autopct='%1.1f%%',
            startangle=90,
            shadow=True,
        )
        
        # Añadir título
        plt.title('Distribución de temas por categoría', fontsize=16)
        
        # Añadir leyenda si hay muchas categorías
        if len(names) > 5:
            plt.legend(loc='best', bbox_to_anchor=(1, 0.5))
        
        # Asegurar que se vea como un círculo
        plt.axis('equal')
        
        # Guardar o mostrar
        if output_file:
            plt.savefig(output_file, bbox_inches='tight')
            logger.info(f"Gráfico guardado en: {output_file}")
        else:
            plt.show()
            
        plt.close()
        
    except Exception as e:
        logger.error(f"Error al generar el gráfico: {str(e)}")

def generate_bar_chart(categories_data, output_file=None):
    """Genera un gráfico de barras con la distribución de temas por categoría."""
    try:
        # Extraer nombres y cantidades
        names = [cat[0] for cat in categories_data]
        values = [cat[1] for cat in categories_data]
        
        # Limitar a las 15 principales categorías si hay más
        if len(names) > 15:
            others_sum = sum(values[14:])
            names = names[:14] + ["Otros"]
            values = values[:14] + [others_sum]
        
        # Crear figura y ejes
        plt.figure(figsize=(14, 8))
        
        # Generar gráfico de barras
        plt.bar(range(len(names)), values, color='royalblue')
        
        # Añadir etiquetas y título
        plt.xlabel('Categoría', fontsize=12)
        plt.ylabel('Número de temas', fontsize=12)
        plt.title('Número de temas por categoría', fontsize=16)
        
        # Añadir etiquetas en el eje X con rotación
        plt.xticks(range(len(names)), names, rotation=45, ha='right')
        
        # Añadir valores en la parte superior de cada barra
        for i, v in enumerate(values):
            plt.text(i, v + 5, str(v), ha='center')
        
        # Ajustar layout
        plt.tight_layout()
        
        # Guardar o mostrar
        if output_file:
            plt.savefig(output_file, bbox_inches='tight')
            logger.info(f"Gráfico guardado en: {output_file}")
        else:
            plt.show()
            
        plt.close()
        
    except Exception as e:
        logger.error(f"Error al generar el gráfico: {str(e)}")

def main():
    # Verificar argumentos
    if len(sys.argv) < 2:
        print("Uso: python analyze_csv.py <archivo_csv> [directorio_salida]")
        print("  <archivo_csv>: Ruta al archivo CSV con los temas")
        print("  [directorio_salida]: Directorio opcional para guardar los gráficos (por defecto: 'stats')")
        return
    
    # Obtener argumentos
    csv_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "stats"
    
    # Crear directorio de salida si no existe
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Leer CSV
    topics = read_csv(csv_file)
    
    if not topics:
        logger.error("No se pudieron leer temas del archivo CSV.")
        return
    
    # Generar estadísticas
    categories_data = print_category_stats(topics)
    
    # Generar nombre de archivo basado en la fecha actual
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generar gráficos
    generate_pie_chart(
        categories_data, 
        output_file=os.path.join(output_dir, f"category_pie_chart_{timestamp}.png")
    )
    
    generate_bar_chart(
        categories_data, 
        output_file=os.path.join(output_dir, f"category_bar_chart_{timestamp}.png")
    )
    
    logger.info(f"Análisis completado. Los gráficos se han guardado en el directorio: {output_dir}")

if __name__ == "__main__":
    main() 