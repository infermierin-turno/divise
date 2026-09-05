import os
import json
import requests
from openai import OpenAI

class ShopifyCoffeeAgent:
    def __init__(self, shop_url, openai_api_key, client_id=None, client_secret=None, **kwargs):
        self.shop_url = shop_url.rstrip('/')
        self.ai_client = OpenAI(api_key=openai_api_key)
        
        self.client_id = client_id or os.getenv("SHOPIFY_CLIENT_ID") or os.getenv("SHOPIFY_API_KEY")
        self.client_secret = client_secret or os.getenv("SHOPIFY_CLIENT_SECRET") or os.getenv("SHOPIFY_SECRET") or os.getenv("SHOPIFY_API_SECRET")
        
        self.access_token = self._get_admin_access_token()
        
        self.headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token if self.access_token else ""
        }

    def _get_admin_access_token(self):
        """Ottiene dinamicamente il token di accesso tramite OAuth client_credentials."""
        if not self.client_id or not self.client_secret:
            print("[AVVISO] Client ID o Client Secret mancanti per la generazione OAuth.")
            return None

        auth_url = f"{self.shop_url}/admin/oauth/access_token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        
        try:
            response = requests.post(auth_url, data=payload)
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                print("[SUCCESSO] Token di accesso Shopify generato correttamente.")
                return token
            else:
                print(f"[AVVISO] OAuth standard non riuscito ({response.status_code}: {response.text}).")
                return self.client_secret
        except Exception as e:
            print(f"Errore durante la richiesta del token Shopify: {e}")
            return None

    def get_products(self, limit=50):
        """Recupera l'elenco dei prodotti tramite Shopify GraphQL Admin API."""
        graphql_url = f"{self.shop_url}/admin/api/2024-07/graphql.json"
        
        query = f"""
        {{
          products(first: {limit}) {{
            edges {{
              node {{
                id
                title
                handle
                descriptionHtml
                tags
              }}
            }}
          }}
        }}
        """
        
        response = requests.post(graphql_url, json={"query": query}, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            products = []
            for edge in edges:
                node = edge.get("node", {})
                raw_id = node.get("id", "")
                numeric_id = raw_id.split("/")[-1] if raw_id else ""
                products.append({
                    "id": numeric_id,
                    "title": node.get("title"),
                    "body_html": node.get("descriptionHtml"),
                    "tags": node.get("tags", [])
                })
            return products
        else:
            print(f"[ERRORE] Impossibile recuperare i prodotti via GraphQL: {response.text}")
            return []

    def get_pending_products(self, limit=3):
        """Restituisce i primi N prodotti che non hanno il tag 'Ottimizzato IA'."""
        all_products = self.get_products(limit=50)
        pending = []
        for p in all_products:
            tags = p.get("tags", [])
            if isinstance(tags, str):
                tags_list = [t.strip() for t in tags.split(",")]
            else:
                tags_list = tags
            
            if "Ottimizzato IA" not in tags_list:
                pending.append(p)
                if len(pending) >= limit:
                    break
        return pending

    def optimize_divise_content(self, title, current_body):
        """Usa l'IA con le regole di rigore, generando lo Schema FAQ esattamente nel formato richiesto."""
        system_prompt = """Sei un copywriter esperto di abbigliamento professionale e divise per i settori sanitario, estetico, sala, cucina, ristorazione e hospitality.

Scrivi descrizioni per un e-commerce professionale. La voce del brand è competente, concreta, affidabile e rassicurante. Il tono è professionale ma naturale, diretto e comprensibile. Usa frasi brevi, verbi attivi e informazioni utili per aiutare il cliente nella scelta.

Metti in evidenza:
- comfort e libertà di movimento;
- vestibilità, vestibilità e comfort;
- tessuti e composizione;
- resistenza ai lavaggi;
- facilità di manutenzione;
- tasche, chiusure, elasticità e dettagli funzionali se presenti nel prodotto originale;
- utilizzo professionale consigliato;
- possibilità di personalizzazione tranne che per i pantaloni e le scarpe.
- made in Italy dal 2007 se presente nell'originale
- il problema o bisogno risolto dal prodotto;
- i principali vantaggi rispetto a prodotti generici;
- taglie, colori e modalità di utilizzo;
- contesti professionali adatti;
- informazioni utili per favorire la decisione d’acquisto;
- una call to action finale chiara e naturale.

REGOLA FONDAMENTALE:
Non inventare mai caratteristiche, materiali, certificazioni, proprietà tecniche, vestibilità, colori, misure o prestazioni non presenti nelle informazioni fornite.

Non descrivere un prodotto come antibatterico, antimacchia, ignifugo, impermeabile, elasticizzato, certificato, traspirante o adatto a uno specifico utilizzo se queste caratteristiche non sono esplicitamente indicate.

Se un'informazione non è disponibile, omettila. Non fare supposizioni e non presentare come certe informazioni generiche normalmente associate a quel tipo di prodotto.

La descrizione HTML deve essere ordinata e leggibile e può contenere:
- un'introduzione con <p>;
- titoli <h2> descrittivi;
- elenchi puntati con <ul> e <li>;
- parole importanti in <strong>.

Non utilizzare <h1>. Non inserire markdown, link, emoji, shortcode o codice JavaScript nel corpo HTML.

REGOLE SEO:
- seo_title: massimo 60 caratteri, chiaro e descrittivo;
- seo_description: idealmente tra 140 e 155 caratteri, naturale e utile per il cliente;
- non inserire parole chiave in modo artificiale.

REGOLE PER IL FAQ SCHEMA:
Genera un array JSON con 3 o 4 domande e risposte utili per il cliente (es. su tessuti, lavaggio, utilizzo o personalizzazione), strutturate esattamente in questo formato:
[
  {
    "@type": "Question",
    "name": "Domanda...",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Risposta..."
    }
  }
]
Bassati unicamente sulle informazioni certe del prodotto.

REGOLE TASSATIVE PER L'OUTPUT:
Devi restituire esclusivamente un oggetto JSON valido con questa struttura esatta:
{
  "seo_title": "Titolo SEO",
  "seo_description": "Descrizione SEO",
  "body_html": "<p>Descrizione HTML...</p>",
  "faq_schema": [
    {
      "@type": "Question",
      "name": "Domanda...",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Risposta..."
      }
    }
  ]
}"""

        user_prompt = f"""
Analizza e riscrivi il seguente prodotto per il nostro e-commerce di abbigliamento professionale.

Nome prodotto:
{title}

Descrizione attuale:
{current_body or "Nessuna descrizione disponibile"}

Usa le informazioni disponibili nella descrizione attuale come fonte principale.
Mantieni tutti i dati tecnici corretti già presenti ed elimina ripetizioni o frasi generiche.
"""

        try:
            response = self.ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content.strip()
            data = json.loads(raw_content)
            return data
        except Exception as e:
            print(f"Errore durante la generazione o il parsing JSON dall'IA: {e}")
            return None

    def update_product_seo_and_description(self, product_id, seo_data, tag_to_add="Ottimizzato IA"):
        """Aggiorna su Shopify descrizione, SEO, tag e salva il FAQ Schema nel Metafield dedicato."""
        graphql_url = f"{self.shop_url}/admin/api/2024-07/graphql.json"
        
        # 1. Recuperiamo i tag attuali
        get_query = f"""
        {{
          product(id: "gid://shopify/Product/{product_id}") {{
            tags
          }}
        }}
        """
        resp = requests.post(graphql_url, json={"query": get_query}, headers=self.headers)
        tags_list = []
        if resp.status_code == 200:
            node = resp.json().get("data", {}).get("product", {})
            if node and node.get("tags"):
                tags_list = node.get("tags")
        
        if tag_to_add not in tags_list:
            tags_list.append(tag_to_add)

        # 2. Mutazione GraphQL per aggiornare prodotto, HTML, SEO e tag
        mutation = """
        mutation productUpdate($input: ProductInput!) {
          productUpdate(input: $input) {
            product {
              id
              title
              descriptionHtml
              tags
              seo {
                title
                description
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        
        variables = {
            "input": {
                "id": f"gid://shopify/Product/{product_id}",
                "descriptionHtml": seo_data.get("body_html"),
                "tags": tags_list,
                "seo": {
                    "title": seo_data.get("seo_title"),
                    "description": seo_data.get("seo_description")
                }
            }
        }
        
        response = requests.post(graphql_url, json={"query": mutation, "variables": variables}, headers=self.headers)
        
        if response.status_code == 200:
            result_data = response.json()
            user_errors = result_data.get("data", {}).get("productUpdate", {}).get("userErrors", [])
            if user_errors:
                print(f"[ERRORE GRAPHQL PRODOTTO] {user_errors}")
                return False
            
            # 3. Salvataggio del Metafield FAQ Schema (namespace: custom, key: faq_schema)
            faq_obj = seo_data.get("faq_schema")
            if faq_obj:
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
                
                meta_resp = requests.post(graphql_url, json={"query": metafield_mutation, "variables": metafield_variables}, headers=self.headers)
                if meta_resp.status_code == 200:
                    meta_data = meta_resp.json()
                    meta_errors = meta_data.get("data", {}).get("metafieldsSet", {}).get("userErrors", [])
                    if meta_errors:
                        print(f"[AVVISO METAFIELD FAQ] {meta_errors}")
                    else:
                        print(f"[SUCCESSO] Metafield FAQ Schema salvato correttamente per il prodotto {product_id}!")
                else:
                    print(f"[ERRORE HTTP METAFIELD] {meta_resp.text}")

            print(f"[SUCCESSO] Prodotto ID {product_id} aggiornato completamente via GraphQL!")
            return True
        else:
            print(f"[ERRORE HTTP PRODOTTO] {response.text}")
            return False
