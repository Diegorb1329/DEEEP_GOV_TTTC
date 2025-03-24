import scrapy
import json

class GitcoinSpider(scrapy.Spider):
    name = "gitcoin"
    allowed_domains = ["gov.gitcoin.co"]
    start_urls = ["https://gov.gitcoin.co/categories"]
    
    # Identificador de la categoría Grants Lab
    GRANTS_LAB_ID = "/c/product/17"
    
    def parse(self, response):
        # Extraer categorías desde la tabla de categorías
        rows = response.css("table.category-list tbody tr")
        self.logger.info(f"Encontradas {len(rows)} filas en la tabla de categorías")
        
        for row in rows:
            # Extraer información de la categoría
            category_td = row.css("td.category")
            
            # Extraer nombre y enlace de la categoría
            category_name = category_td.css("h3 a span::text").get()
            category_url = response.urljoin(category_td.css("h3 a::attr(href)").get())
            
            # Extraer descripción
            description = category_td.css("div[itemprop='description']::text").get()
            
            # Extraer número de temas
            topics_count = row.css("td.topics div::text").get()
            
            # Estilo (color)
            category_style = category_td.css("::attr(style)").get()
            
            category_data = {
                "name": category_name.strip() if category_name else None,
                "url": category_url,
                "description": description.strip() if description else None,
                "topics_count": topics_count.strip() if topics_count else None,
                "style": category_style
            }
            
            # Verificar si es la categoría "Grants Lab"
            is_grants_lab = self.GRANTS_LAB_ID in category_url
            
            # Hacer seguimiento a la URL de la categoría para obtener los temas
            yield scrapy.Request(
                url=category_url,
                callback=self.parse_category,
                meta={"category": category_data, "is_grants_lab": is_grants_lab}
            )
    
    def parse_category(self, response):
        category = response.meta["category"]
        is_grants_lab = response.meta["is_grants_lab"]
        
        # Extraer los temas de la categoría
        topics = response.css("tr.topic-list-item")
        
        # Crear objeto para almacenar la información de la categoría y sus temas
        category_with_topics = {
            "category": category,
            "topics": []
        }
        
        # Extraer todos los temas en lugar de limitar a 5
        for topic in topics:
            title_element = topic.css("a.title::text").get()
            url_element = topic.css("a.title::attr(href)").get()
            
            # Solo procesar si podemos obtener al menos el título y la URL
            if title_element and url_element:
                # Extraer los campos con manejo seguro de valores nulos
                replies = topic.css("td.num.posts::text").get()
                views = topic.css("td.num.views::text").get()
                activity = topic.css("td.num.activity a::text").get()
                
                topic_data = {
                    "title": title_element.strip(),
                    "url": response.urljoin(url_element),
                    "replies": replies.strip() if replies else None,
                    "views": views.strip() if views else None,
                    "activity": activity.strip() if activity else None
                }
                category_with_topics["topics"].append(topic_data)
                
                # Seguir todos los enlaces a los temas para extraer contenido detallado
                # independientemente de la categoría
                yield scrapy.Request(
                    url=response.urljoin(url_element),
                    callback=self.parse_topic,
                    meta={"topic_data": topic_data}
                )
        
        # Verificar si hay paginación y seguir a la siguiente página
        next_page = response.css("div.pagination a.btn.btn-icon.btn-flat.btn-default.next::attr(href)").get()
        if next_page:
            yield scrapy.Request(
                url=response.urljoin(next_page),
                callback=self.parse_category,
                meta={"category": category, "is_grants_lab": is_grants_lab}
            )
            
        yield category_with_topics
    
    def parse_topic(self, response):
        """Extraer el contenido detallado de un tema específico"""
        topic_data = response.meta["topic_data"]
        
        # Extraer los posts del tema usando la estructura correcta
        posts = response.css("div.topic-body.crawler-post")
        
        if posts:
            # Extraer información del post inicial
            post_initial = posts[0]
            
            # Extraer la información del autor
            author = post_initial.css("span.creator a span::text").get()
            author_url = response.urljoin(post_initial.css("span.creator a::attr(href)").get()) if post_initial.css("span.creator a::attr(href)").get() else None
            
            # Extraer fecha
            post_date = post_initial.css("time.post-time::text").get()
            
            # Extraer contenido del post inicial
            post_content = "".join(post_initial.css("div.post p::text, div.post p strong::text").getall())
            
            # Extraer las respuestas (todos los posts excepto el primero)
            replies = []
            for post in posts[1:]:
                reply_author = post.css("span.creator a span::text").get()
                reply_date = post.css("time.post-time::text").get()
                reply_content = "".join(post.css("div.post p::text, div.post p strong::text").getall())
                
                replies.append({
                    "author": reply_author.strip() if reply_author else None,
                    "date": reply_date.strip() if reply_date else None,
                    "content": reply_content.strip() if reply_content else None
                })
            
            # Crear el objeto con la información detallada del tema
            detailed_topic = {
                "title": topic_data["title"],
                "url": topic_data["url"],
                "author": author.strip() if author else None,
                "author_url": author_url,
                "date": post_date.strip() if post_date else None,
                "content": post_content.strip() if post_content else None,
                "replies_count": len(replies),
                "replies": replies
            }
            
            yield detailed_topic