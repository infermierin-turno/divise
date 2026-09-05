import os
import requests
from fastapi import FastAPI, HTTPException
from shopify_agent import ShopifyCoffeeAgent

app = FastAPI(title="Shopify Divise SEO & AI Agent")

shop_url = os.getenv("SHOP_URL") or "[https://1a6ed6.myshopify.com](https://1a6ed6.myshopify.com)"
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
    """Panoramica dei comandi disponibili per il controllo umano."""
    return {
        "status": "online",
        "shop": shop_url,
        "azioni_disponibili": {
            "1_mostra_primi_tre_da_ottimizzare": "/pending-products",
            "2_anteprima_correzione": "/preview/{product_id}",
            "3_approva_e_applica": "/apply/{product_id}"
        }
    }

@app.get("/pending-products")
def get_pending_products():
    """Mostra i primi tre articoli in sospeso (escludendo quelli con tag 'Ottimizzato IA')."""
    try:
        pending = agent.get_pending_products(limit=3)
        return {
            "status": "success",
            "count": len(pending),
            "products_to_optimize": [
                {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "preview_link": f"/preview/{p.get('id')}"
                } for p in pending
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/preview/{product_id}")
def preview_product_optimization(product_id: str):
    """Mostra l'anteprima della correzione IA per un prodotto specifico senza scriverla su Shopify."""
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
            raise HTTPException(status_code=500, detail="Errore durante la generazione dell'anteprima IA.")
        
        return {
            "status": "preview_ready",
            "product_id": product_id,
            "original_title": title,
            "original_body_html": current_body,
            "proposed_optimization": seo_data,
            "approva_e_scrivi_link": f"/apply/{product_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/apply/{product_id}")
def apply_product_optimization(product_id: str):
    """Approva l'anteprima: aggiorna Shopify e applica il tag 'Ottimizzato IA' per saltarlo in futuro."""
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
            raise HTTPException(status_code=500, detail="Errore durante la generazione SEO.")
        
        success = agent.update_product_seo_and_description(product_id, seo_data, tag_to_add="Ottimizzato IA")
        if success:
            return {
                "status": "approved_and_applied",
                "product_id": product_id,
                "title": title,
                "applied_data": seo_data,
                "tag_added": "Ottimizzato IA",
                "next_step": "Vai su /pending-products per vedere i prossimi articoli."
            }
        else:
            raise HTTPException(status_code=500, detail="Errore durante l'aggiornamento su Shopify.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
