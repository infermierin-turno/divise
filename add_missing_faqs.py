import json
import os
from dotenv import load_dotenv
from tuofile import ShopifyCoffeeAgent  # Sostituisci 'tuofile' con il nome reale del file .py dove si trova la classe

# Carica le variabili d'ambiente (se usi un file .env)
load_dotenv()

# Configura le credenziali del tuo store
SHOP_URL = os.getenv("SHOPIFY_SHOP_URL", "https://iltuosito.myshopify.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "la-tua-openai-api-key")
CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")

def generate_default_faq(product_title, variants):
    """Genera un FAQ Schema di fallback basato sul titolo e sulle varianti del prodotto."""
    variants_text = ", ".join([v.get("title", "") for v in variants if v.get("title")]) if variants kes "Nessuna variante specifica"
    
    faq_list = [
        {
            "@type": "Question",
            "name": f"Quali sono le caratteristiche principali di {product_title}?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"Il capo {product_title} è progettato per garantire comfort, praticità e resistenza in ambito professionale."
            }
        },
        {
            "@type": "Question",
            "name": f"Quali varianti o taglie sono disponibili per {product_title}?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"Il prodotto è disponibile nelle seguenti opzioni: {variants_text}."
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
    
    # 1. Recuperiamo tutti i prodotti con le relative varianti e controlliamo se hanno già il metafield 'faq_schema'
    print("[INFO] Recupero dei prodotti dallo store...")
    query = """
    {
      products(first: 250) {
        edges {
          node {
            id
            title
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
        has_faq_metafield = node.get("metafield") is not None

        if has_faq_metafield:
            print(f"[SALTO] Il prodotto '{title}' (ID: {product_id}) ha già il metafield FAQ.")
            continue

        print(f"[ELABORAZIONE] Aggiunta FAQ Schema mancante per: '{title}' (ID: {product_id})...")
        
        # Estrae le varianti
        variants_list = []
        for v_edge in node.get("variants", {}).get("edges", []):
            variants_list.append(v_edge.get("node", {}))

        # Genera le FAQ standard/strutturate per questo articolo
        faq_obj = generate_default_faq(title, variants_list)

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
                print(f"[SUCCESSO] FAQ Schema inserito per '{title}'!")
                updated_count += 1
        else:
            print(f"[ERRORE HTTP] {meta_resp.text}")

    print(f"\n[COMPLETATO] Processo terminato. Aggiunti FAQ Schema a {updated_count} prodotti.")

def requests_post_safe(url, query, headers):
    import requests
    try:
        return requests.post(url, json={"query": query}, headers=headers)
    except Exception as e:
        print(f"Errore di rete: {e}")
        return None

if __name__ == "__main__":
    bulk_add_missing_faqs()
