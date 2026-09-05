import os
import json
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
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

def generate_complete_faq(product_title, variants, body_html=""):
    """Genera un blocco FAQ Schema completo (4 domande professionali) basato su titolo, varianti e descrizione."""
    variants_text = ", ".join([v.get("title", "") for v in variants if v.get("title")]) if variants else "Diverse opzioni disponibili"
    
    clean_body_snippet = "progettato per garantire il massimo comfort e praticità in ambito lavorativo."
    if body_html and len(body_html) > 30:
        clean_body_snippet = "ideale per chi opera in contesti professionali grazie a materiali resistenti e funzionali."

    faq_list = [
        {
            "@type": "Question",
            "name": f"Quali sono le caratteristiche principali di {product_title}?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"Il capo {product_title} è {clean_body_snippet} Assicura un'ottima resa estetica e una lunga durata nel tempo."
            }
        },
        {
            "@type": "Question",
            "name": f"Quali taglie o varianti sono disponibili per {product_title}?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"Il prodotto è disponibile nelle seguenti varianti: {variants_text}. Per la scelta della misura corretta, puoi consultare la nostra <a href=\"/pages/guida-alle-taglie\">guida alle taglie</a>."
            }
        },
        {
            "@type": "Question",
            "name": "Come bisogna curare e lavare questo capo professionale?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "I nostri capi professionali sono studiati per resistere a lavaggi frequenti. Si consiglia di seguire le indicazioni riportate sull'etichetta interna per preservare al meglio i colori e la consistenza del tessuto."
            }
        },
        {
            "@type": "Question",
            "name": "È possibile personalizzare il prodotto con il logo aziendale?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "Sì, la maggior parte dei nostri capi di abbigliamento professionale può essere personalizzata con ricami o stampe del proprio logo. Contattaci per maggiori informazioni sui servizi di personalizzazione."
            }
        }
    ]
    return faq_list

def requests_post_safe(url, query, headers, variables=None):
    try:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        return requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Errore di rete: {e}")
        return None

def bulk_add_missing_faqs():
    graphql_url = f"{agent.shop_url}/admin/api/2024-07/graphql.json"
    updated_count = 0
    has_next_page = True
    end_cursor = None

    # Ciclo di paginazione per scorrere tutto il catalogo di Shopify
    while has_next_page:
        query = """
        query getProducts($cursor: String) {
          products(first: 250, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                id
                title
                descriptionHtml
                variants(first: 20) {
                  edges {
                    node {
                      title
                    }
                  }
                }
                metafield(namespace: "custom", key: "faq_schema") {
                  id
                }
              }
            }
          }
        }
        """
        variables = {"cursor": end_cursor}
        response = requests_post_safe(graphql_url, query, agent.headers, variables=variables)
        
        if not response or response.status_code != 200:
            raise Exception("Impossibile recuperare l'elenco dei prodotti da Shopify.")

        data = response.json().get("data", {}).get("products", {})
        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")

        edges = data.get("edges", [])

        for edge in edges:
            node = edge.get("node", {})
            raw_id = node.get("id", "")
            product_id = raw_id.split("/")[-1] if raw_id else ""
            title = node.get("title", "Prodotto")
            body_html = node.get("descriptionHtml", "")
            has_faq_metafield = node.get("metafield") is not None

            if has_faq_metafield:
                continue

            variants_list = []
            for v_edge in node.get("variants", {}).get("edges", []):
                variants_list.append(v_edge.get("node", {}))

            faq_obj = generate_complete_faq(title, variants_list, body_html)

            metafield_mutation = """
            mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
              metafieldsSet(metafields: $metafields) {
                metafields {
                  id
                  namespace
                  key
                  value
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            metafield_variables = {
                "metafields": [
                    {
                        "ownerId": f"gid://shopify/Product/{product_id}",
                        "namespace": "custom",
                        "key": "faq_schema",
                        "type": "json",
                        "value": json.dumps(faq_obj, ensure_ascii=False)
                    }
                ]
            }

            meta_resp = requests.post(graphql_url, json={"query": metafield_mutation, "variables": metafield_variables}, headers=agent.headers)
            if meta_resp.status_code == 200:
                meta_data = meta_resp.json()
                meta_errors = meta_data.get("data", {}).get("metafieldsSet", {}).get("userErrors", [])
                if not meta_errors:
                    updated_count += 1

    return updated_count

@app.get("/run-bulk-faqs")
def trigger_bulk_faqs(key: str = ""):
    """Endpoint protetto per avviare l'aggiornamento massivo delle FAQ sui prodotti mancanti."""
    secret_key = os.getenv("BULK_SECRET_KEY", "unasegretafacile")
    if key != secret_key:
        raise HTTPException(status_code=403, detail="Non autorizzato: chiave errata o mancante.")

    try:
        count = bulk_add_missing_faqs()
        return {"status": "success", "message": f"Aggiornamento massivo completato. Aggiunti FAQ Schema a {count} prodotti in tutto il catalogo."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Dashboard principale."""
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
                <p class="text-gray-600 mb-6">Scegli come procedere con l'ottimizzazione SEO dei prodotti:</p>
                
                <!-- SEZIONE 1: RICERCA PUNTUALE PER ID -->
                <div class="mb-8 p-5 bg-blue-50/50 rounded-xl border border-blue-100">
                    <h3 class="text-sm font-bold text-blue-900 uppercase tracking-wide mb-2">1. Cerca e aggiorna un prodotto specifico</h3>
                    <p class="text-xs text-gray-500 mb-3">Inserisci l'ID numerico del prodotto per forzare l'ottimizzazione.</p>
                    <form action="/preview-custom" method="get" class="flex gap-3">
                        <input type="text" name="product_id" placeholder="ID Prodotto Shopify" required
                            class="flex-1 px-4 py-2 border rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2 rounded-lg text-sm transition shadow">
                            Ottimizza per ID
                        </button>
                    </form>
                </div>

                <!-- SEZIONE 2: AGGIORNAMENTO MASSIVO FAQ -->
                <div class="mb-8 p-5 bg-purple-50/50 rounded-xl border border-purple-100">
                    <h3 class="text-sm font-bold text-purple-900 uppercase tracking-wide mb-2">2. Aggiornamento Massivo FAQ Schema (Completo)</h3>
                    <p class="text-xs text-gray-500 mb-3">Scansiona tutto il catalogo e aggiunge le FAQ strutturate a tutti i prodotti rimanenti.</p>
                    <a href="/run-bulk-faqs?key=unasegretafacile" target="_blank" class="inline-block bg-purple-600 hover:bg-purple-700 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition shadow">
                        Esegui Aggiornamento Massivo Totale &rarr;
                    </a>
                </div>

                <!-- SEZIONE 3: PRODOTTI IN SOSPESO -->
                <div class="p-5 bg-gray-50 rounded-xl border border-gray-200">
                    <h3 class="text-sm font-bold text-gray-800 uppercase tracking-wide mb-2">3. Prodotti in sospeso</h3>
                    <p class="text-xs text-gray-500 mb-4">Visualizza l'elenco dei prodotti che non possiedono ancora il tag "Ottimizzato IA".</p>
                    <a href="/pending-products" class="inline-block bg-gray-800 hover:bg-gray-900 text-white font-medium px-5 py-2.5 rounded-lg shadow transition text-sm">
                        Visualizza Prodotti in Sospeso &rarr;
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
                        <p class="text-sm text-gray-500">Articoli non ancora ottimizzati</p>
                    </div>
                    <a href="/" class="text-blue-600 hover:underline text-sm font-medium">&larr; Torna alla Home</a>
                </header>
                <div class="space-y-4">{cards_html}</div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/preview-custom", response_class=HTMLResponse)
def preview_custom_product(product_id: str):
    clean_id = product_id.strip().split("/")[-1]
    return preview_product_optimization(clean_id)

@app.get("/preview/{product_id}", response_class=HTMLResponse)
def preview_product_optimization(product_id: str):
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
            <div class="max-w-6xl mx-auto p-8">
                <header class="mb-8 border-b pb-4 flex justify-between items-center">
                    <div>
                        <h1 class="text-2xl font-bold text-gray-800">Anteprima Ottimizzazione</h1>
                        <p class="text-sm text-gray-500">Prodotto: <strong class="text-gray-700">{title}</strong> (ID: {product_id})</p>
                    </div>
                    <a href="/" class="text-blue-600 hover:underline text-sm font-medium">&larr; Torna alla Home</a>
                </header>

                <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                    <div class="bg-white border rounded-xl p-6 shadow-sm flex flex-col justify-between">
                        <div>
                            <h3 class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4 pb-2 border-b">Situazione Attuale (Originale)</h3>
                            <div class="mb-4">
                                <span class="text-xs font-bold text-gray-500 block mb-1">Titolo Prodotto:</span>
                                <p class="text-gray-800 font-medium text-base">{title}</p>
                            </div>
                            <div>
                                <span class="text-xs font-bold text-gray-500 block mb-1">Descrizione HTML Attuale:</span>
                                <div class="text-sm text-gray-700 bg-gray-50 p-4 rounded-lg border h-96 overflow-y-auto font-mono mt-1 leading-relaxed">
                                    {current_body if current_body else '<em>Nessuna descrizione presente</em>'}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="bg-white border border-green-300 rounded-xl p-6 shadow-md bg-green-50/20 flex flex-col justify-between">
                        <div>
                            <h3 class="text-xs font-bold text-green-700 uppercase tracking-wider mb-4 pb-2 border-b border-green-200">Proposta IA (Ottimizzata)</h3>
                            <div class="mb-3">
                                <span class="text-xs font-bold text-gray-500 block mb-1">Meta Title:</span>
                                <p class="text-blue-700 font-semibold text-base bg-blue-50/50 p-2 rounded border border-blue-100">{seo_title}</p>
                            </div>
                            <div class="mb-4">
                                <span class="text-xs font-bold text-gray-500 block mb-1">Meta Description:</span>
                                <p class="text-gray-700 text-sm bg-gray-50/80 p-2.5 rounded border border-gray-200">{seo_desc}</p>
                            </div>
                            <div>
                                <span class="text-xs font-bold text-gray-500 block mb-1">Nuovo HTML Ottimizzato:</span>
                                <div class="text-sm text-gray-800 bg-white p-4 rounded-lg border border-green-200 h-96 overflow-y-auto font-mono mt-1 leading-relaxed">
                                    {body_html}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex justify-end gap-4 bg-white p-5 rounded-xl border shadow-sm items-center">
                    <a href="/" class="px-6 py-2.5 rounded-lg border text-gray-700 hover:bg-gray-50 font-medium text-sm transition">Annulla</a>
                    <a href="/apply/{product_id}" class="px-8 py-3 rounded-lg bg-green-600 hover:bg-green-700 text-white font-semibold text-sm shadow-md transition">Approva e Scrivi su Shopify &rarr;</a>
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
                    <p class="text-gray-600 mb-6">Il prodotto <strong>{title}</strong> è stato aggiornato su Shopify.</p>
                    <a href="/" class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-3 rounded-lg shadow transition">
                        Torna alla Home &rarr;
                    </a>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)
        else:
            raise HTTPException(status_code=500, detail="Errore durante l'aggiornamento su Shopify.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
