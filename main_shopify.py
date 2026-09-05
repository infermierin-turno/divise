import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
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

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Dashboard principale con interfaccia grafica e pulsanti di navigazione."""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <title>Divise & Divise - SEO Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-50 text-gray-900 font-sans antialiased">
        <div class="max-w-4xl mx-auto p-8">
            <header class="mb-8 border-b pb-4 flex justify-between items-center">
                <div>
                    <h1 class="text-3xl font-bold text-blue-600">Divise & Divise</h1>
                    <p class="text-sm text-gray-500">Agente SEO IA connesso a: {shop_url}</p>
                </div>
                <span class="px-3 py-1 bg-green-100 text-green-800 text-xs font-semibold rounded-full">Online</span>
            </header>

            <div class="bg-white rounded-xl shadow-md p-6 mb-6">
                <h2 class="text-xl font-semibold mb-4">Pannello di Controllo</h2>
                <p class="text-gray-600 mb-6">Gestisci l'ottimizzazione SEO automatica dei prodotti del catalogo con un solo clic. I prodotti ottimizzati vengono automaticamente contrassegnati per evitare duplicazioni.</p>
                
                <div class="flex gap-4">
                    <a href="/pending-products" class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-3 rounded-lg shadow transition text-center flex-1">
                        Visualizza Prodotti in Sospeso
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/pending-products", response_class=HTMLResponse)
def get_pending_products():
    """Mostra in formato HTML i primi tre articoli in sospeso con pulsanti per l'anteprima."""
    try:
        pending = agent.get_pending_products(limit=3)
        
        cards_html = ""
        if not pending:
            cards_html = '<div class="p-6 bg-green-50 text-green-700 rounded-lg text-center font-medium">Ottimo lavoro! Tutti i prodotti sono stati ottimizzati.</div>'
        else:
            for p in pending:
                pid = p.get('id')
                title = p.get('title')
                cards_html += f"""
                <div class="bg-white border border-gray-200 rounded-xl p-5 mb-4 shadow-sm flex justify-between items-center">
                    <div>
                        <span class="text-xs font-mono text-gray-400">ID: {pid}</span>
                        <h3 class="text-lg font-semibold text-gray-800">{title}</h3>
                    </div>
                    <a href="/preview/{pid}" class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
                        Genera Anteprima
                    </a>
                </div>
                """

        html_content = f"""
        <!DOCTYPE html>
        <html lang="it">
        <head>
            <meta charset="UTF-8">
            <title>Prodotti in Sospeso - Divise & Divise</title>
            <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
        </head>
        <body class="bg-gray-50 text-gray-900 font-sans antialiased">
            <div class="max-w-4xl mx-auto p-8">
                <header class="mb-8 border-b pb-4 flex justify-between items-center">
                    <div>
                        <h1 class="text-2xl font-bold text-gray-800">Prodotti in Sospeso</h1>
                        <p class="text-sm text-gray-500">Primi 3 articoli non ancora ottimizzati</p>
                    </div>
                    <a href="/" class="text-blue-600 hover:underline text-sm font-medium">&larr; Torna alla Home</a>
                </header>

                <div class="space-y-4">
                    {cards_html}
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/preview/{product_id}", response_class=HTMLResponse)
def preview_product_optimization(product_id: str):
    """Mostra l'anteprima visiva della correzione IA con pulsanti di approvazione o ritorno."""
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
        
        seo_title = seo_data.get("seo_title", "")
        seo_desc = seo_data.get("seo_description", "")
        body_html = seo_data.get("body_html", "")

        html_content = f"""
        <!DOCTYPE html>
        <html lang="it">
        <head>
            <meta charset="UTF-8">
            <title>Anteprima Ottimizzazione SEO</title>
            <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
        </head>
        <body class="bg-gray-50 text-gray-900 font-sans antialiased">
            <div class="max-w-4xl mx-auto p-8">
                <header class="mb-8 border-b pb-4 flex justify-between items-center">
                    <div>
                        <h1 class="text-2xl font-bold text-gray-800">Anteprima Ottimizzazione</h1>
                        <p class="text-sm text-gray-500">Prodotto: {title}</p>
                    </div>
                    <a href="/pending-products" class="text-blue-600 hover:underline text-sm font-medium">&larr; Indietro ai prodotti</a>
                </header>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                    <div class="bg-white border rounded-xl p-6 shadow-sm">
                        <h3 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Situazione Attuale</h3>
                        <div class="mb-4">
                            <span class="text-xs font-bold text-gray-500">Titolo:</span>
                            <p class="text-gray-800 font-medium">{title}</p>
                        </div>
                        <div>
                            <span class="text-xs font-bold text-gray-500">HTML Attuale:</span>
                            <div class="text-xs text-gray-600 bg-gray-50 p-3 rounded border max-h-48 overflow-y-auto font-mono mt-1">{current_body}</div>
                        </div>
                    </div>

                    <div class="bg-white border border-green-200 rounded-xl p-6 shadow-sm bg-green-50/30">
                        <h3 class="text-sm font-semibold text-green-600 uppercase tracking-wider mb-3">Proposta IA (Ottimizzata)</h3>
                        <div class="mb-3">
                            <span class="text-xs font-bold text-gray-500">Meta Title ({len(seo_title)} caratteri):</span>
                            <p class="text-blue-600 font-semibold">{seo_title}</p>
                        </div>
                        <div class="mb-3">
                            <span class="text-xs font-bold text-gray-500">Meta Description ({len(seo_desc)} caratteri):</span>
                            <p class="text-gray-700 text-sm">{seo_desc}</p>
                        </div>
                        <div>
                            <span class="text-xs font-bold text-gray-500">Nuovo HTML:</span>
                            <div class="text-xs text-gray-600 bg-white p-3 rounded border max-h-48 overflow-y-auto font-mono mt-1">{body_html}</div>
                        </div>
                    </div>
                </div>

                <div class="flex justify-end gap-4 bg-white p-4 rounded-xl border shadow-sm">
                    <a href="/pending-products" class="px-5 py-2.5 rounded-lg border text-gray-700 hover:bg-gray-50 font-medium text-sm">Annulla</a>
                    <a href="/apply/{product_id}" class="px-6 py-2.5 rounded-lg bg-green-600 hover:bg-green-700 text-white font-medium text-sm shadow">Approva e Scrivi su Shopify</a>
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/apply/{product_id}", response_class=HTMLResponse)
def apply_product_optimization(product_id: str):
    """Applica l'ottimizzazione su Shopify, aggiunge il tag e mostra la pagina di successo."""
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
            html_content = f"""
            <!DOCTYPE html>
            <html lang="it">
            <head>
                <meta charset="UTF-8">
                <title>Ottimizzazione Completata</title>
                <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
            </head>
            <body class="bg-gray-50 text-gray-900 font-sans antialiased">
                <div class="max-w-xl mx-auto p-12 text-center mt-12 bg-white rounded-2xl shadow-md border">
                    <div class="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">&#10003;</div>
                    <h1 class="text-2xl font-bold text-gray-800 mb-2">Aggiornato con Successo!</h1>
                    <p class="text-gray-600 mb-6">Il prodotto <strong>{title}</strong> è stato aggiornato su Shopify e taggato come <span class="bg-gray-100 font-mono text-xs px-2 py-1 rounded">Ottimizzato IA</span>.</p>
                    <div class="flex justify-center gap-4">
                        <a href="/pending-products" class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg shadow transition">
                            Passa al prossimo prodotto &rarr;
                        </a>
                    </div>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)
        else:
            raise HTTPException(status_code=500, detail="Errore durante l'aggiornamento su Shopify.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
