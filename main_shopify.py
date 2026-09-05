import os
from fastapi import FastAPI, HTTPException
from shopify_agent import ShopifyCoffeeAgent
from openai import OpenAI

app = FastAPI(title="Shopify Divise SEO & AI Agent")

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

ai_debugger = OpenAI(api_key=openai_api_key)

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

@app.get("/debug-shopify")
def debug_shopify_with_ai():
    import requests
    """Interroga direttamente Shopify e chiede a OpenAI di analizzare perché l'array è vuoto."""
    url = f"{shop_url}/admin/api/2024-07/products.json?status=any"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": agent.access_token if agent.access_token else ""
    }
    
    response = requests.get(url, headers=headers)
    response_text = response.text
    status_code = response.status_code
    
    # Chiediamo a OpenAI di analizzare la risposta di Shopify
    prompt = f"""
    Sto sviluppando un'integrazione con Shopify Admin API.
    Ho fatto una richiesta GET a: {url}
    Il Server ha risposto con Status Code: {status_code}
    Il corpo della risposta è: {response_text}
    
    Tuttavia, il pannello di amministrazione Shopify mostra che i prodotti ci sono. 
    Analizza la risposta e spiega in modo tecnico qual è la causa del problema (es. permessi mancanti, token errato, versione API, o filtri) e come risolverlo.
    """
    
    ai_response = ai_debugger.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return {
        "status_code": status_code,
        "raw_shopify_response": response_text,
        "openai_diagnosis": ai_response.choices[0].message.content
    }
