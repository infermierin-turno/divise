import os
from fastapi import FastAPI
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
