import json
import os
import requests
from dotenv import load_dotenv
from tuofile import ShopifyCoffeeAgent  # Sostituisci 'tuofile' con il nome reale del file .py dove si trova la classe

# Carica le variabili d'ambiente (se usi un file .env)
load_dotenv()

# Configura le credenziali del tuo store
SHOP_URL = os.getenvshop_url = os.getenv("SHOP_URL") or "https://1a6ed6.myshopify.com"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "la-tua-openai-api-key")
CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")

def generate_complete_faq(product_title, variants, body_html=""):
    """Genera un blocco FAQ Schema completo (4 domande professionali) basato su titolo, varianti e descrizione."""
    variants_text = ", ".join([v.get("title", "") for v in variants if v.get("title")]) if variants else "Diverse opzioni disponibili"
    
    # Pulizia minima del body html se presente per estrarre qualche indizio testuale
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
                "text": f"Il prodotto è disponibile nelle seguenti varianti: {variants_text}. Per la scelta della misura corretta, puoi consultare la nostra guida alle taglie."
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

def bulk_add_missing_faqs():
    print("[INFO] Inizializzazione agente Shopify...")
    agent = ShopifyCoffeeAgent(
        shop_url=SHOP_URL,
        openai_api_key=OPENAI_API_KEY,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )

    graphql_url = f"{agent.shop_url}/admin/api/2024-07/graphql.json"
    
    # 1. Recuperiamo tutti i prodotti con varianti, descrizione HTML e controllo metafield 'faq_schema'
    print("[INFO] Recupero dei prodotti dallo store...")
    query = """
    {
      products(first: 250) {
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

    response = requests_post_safe(graphql_url, query, agent.headers)
    if not response or response.status_code != 200:
        print("[ERRORE] Impossibile recuperare l'elenco dei prodotti.")
        return

    edges = response.json().get("data", {}).get("products", {}).get("edges", [])
    print(f"[INFO] Trovati {len(edges)} prodotti totali nello store.")

    updated_count = 0

    for edge in edges:
        node = edge.get("node", {})
        raw_id = node.get("id", "")
        product_id = raw_id.split("/")[-1] if raw_id else ""
        title = node.get("title", "Prodotto")
        body_html = node.get("descriptionHtml", "")
        has_faq_metafield = node.get("metafield") is not None

        if has_faq_metafield:
            print(f"[SALTO] Il prodotto '{title}' (ID: {product_id}) ha già il metafield FAQ.")
            continue

        print(f"[ELABORAZIONE] Generazione FAQ complete per: '{title}' (ID: {product_id})...")
        
        # Estrae le varianti
        variants_list = []
        for v_edge in node.get("variants", {}).get("edges", []):
            variants_list.append(v_edge.get("node", {}))

        # Genera il set completo di FAQ strutturate
        faq_obj = generate_complete_faq(title, variants_list, body_html)

        # Scrive il metafield su Shopify tramite GraphQL
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
            if meta_errors:
                print(f"[ERRORE METAFIELD] {meta_errors}")
            else:
                print(f"[SUCCESSO] FAQ Schema completo inserito per '{title}'!")
                updated_count += 1
        else:
            print(f"[ERRORE HTTP] {meta_resp.text}")

    print(f"\n[COMPLETATO] Processo terminato. Aggiunti FAQ Schema completi a {updated_count} prodotti.")

def requests_post_safe(url, query, headers):
    try:
        return requests.post(url, json={"query": query}, headers=headers)
    except Exception as e:
        print(f"Errore di rete: {e}")
        return None

if __name__ == "__main__":
    bulk_add_missing_faqs()
