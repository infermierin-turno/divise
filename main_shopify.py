import os
from fastapi import FastAPI, HTTPException
from shopify_agent import ShopifyCoffeeAgent

app = FastAPI(title="Shopify Divise SEO & AI Agent")

# Legge correttamente la variabile SHOP_URL configurata su Render (fallback su divisedivise.it)
shop_url = os.getenv("SHOP_URL") or os.getenv("SHOPIFY_SHOP_URL", "https://divisedivise.it")
openai_api_key = os.getenv("OPENAI_API_KEY")
client_id = os.getenv("SHOPIFY_CLIENT_ID")
client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")

agent = ShopifyCoffeeAgent(
    shop_url=shop_url,
    openai_api_key=openai_api_key,
    client_id=client_id,
    client_secret=client_secret
)

@app.get("/")
def read_root():
    """Verifica lo stato del servizio e testa il recupero dei prodotti da Shopify."""
    try:
        products = agent.get_products(limit=5)
        return {
            "status": "online",
            "shop": shop_url,
            "connection_test": "success" if products is not None else "failed",
            "products_count_retrieved": len(products) if products else 0,
            "products_preview": [{"id": p.get("id"), "title": p.get("title")} for p in products] if products else []
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/optimize-products")
def optimize_products(limit: int = 10):
    """Avvia il processo di ottimizzazione IA (SEO + HTML) per i prodotti di Shopify."""
    products = agent.get_products(limit=limit)
    if not products:
        raise HTTPException(status_code=404, detail="Nessun prodotto trovato o errore di connessione con Shopify.")
    
    results = []
    for p in products:
        prod_id = p.get("id")
        title = p.get("title")
        body = p.get("body_html") or ""
        
        seo_data = agent.optimize_divise_content(title, body)
        if seo_data:
            success = agent.update_product_seo_and_description(prod_id, seo_data)
            results.append({
                "product_id": prod_id,
                "title": title,
                "success": success,
                "seo_title_generated": seo_data.get("seo_title")
            })
        else:
            results.append({
                "product_id": prod_id,
                "title": title,
                "success": False,
                "error": "Generazione IA fallita o formato non valido"
            })
            
    return {
        "status": "completed",
        "processed_products": len(results),
        "details": results
    }
