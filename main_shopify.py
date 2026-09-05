import os
import requests
from fastapi import FastAPI, HTTPException
from shopify_agent import ShopifyCoffeeAgent

app = FastAPI(title="Shopify Divise SEO & AI Agent")

shop_url = os.getenv("SHOP_URL") or "https://1a6ed6.myshopify.com"
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
            "products_count_retrieved": len(products) if products else 0,
            "products_preview": [{"id": p.get("id"), "title": p.get("title")} for p in products] if products else []
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/optimize/{product_id}")
def optimize_single_product(product_id: str):
    """Ottimizza SEO e descrizione HTML per uno specifico prodotto tramite IA."""
    try:
        url = f"{agent.shop_url}/admin/api/2024-07/products/{product_id}.json"
        response = requests.get(url, headers=agent.headers)
        
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Prodotto non trovato su Shopify.")
        
        product_data = response.json().get("product", {})
        title = product_data.get("title", "")
        current_body = product_data.get("body_html", "") or ""
        
        seo_data = agent.optimize_divise_content(title, current_body)
        if not seo_data:
            raise HTTPException(status_code=500, detail="Errore durante la generazione dei contenuti SEO con l'IA.")
        
        success = agent.update_product_seo_and_description(product_id, seo_data)
        if success:
            return {
                "status": "success",
                "product_id": product_id,
                "title": title,
                "optimized_data": seo_data
            }
        else:
            raise HTTPException(status_code=500, detail="Errore durante l'aggiornamento del prodotto su Shopify.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize-all")
def optimize_all_products(limit: int = 5):
    """Ottimizza in blocco i primi N prodotti del catalogo."""
    try:
        products = agent.get_products(limit=limit)
        results = []
        
        for p in products:
            prod_id = str(p.get("id"))
            title = p.get("title", "")
            current_body = p.get("body_html", "") or ""
            
            seo_data = agent.optimize_divise_content(title, current_body)
            if seo_data:
                success = agent.update_product_seo_and_description(prod_id, seo_data)
                results.append({
                    "product_id": prod_id,
                    "title": title,
                    "success": success,
                    "optimized_data": seo_data if success else None
                })
            else:
                results.append({
                    "product_id": prod_id,
                    "title": title,
                    "success": False,
                    "error": "Fallita generazione IA"
                })
                
        return {
            "status": "completed",
            "total_processed": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
