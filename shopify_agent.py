import os
import json
import requests
from openai import OpenAI

class ShopifyCoffeeAgent:
    def __init__(self, shop_url, openai_api_key, client_id=None, client_secret=None, access_token=None, **kwargs):
        self.shop_url = shop_url.rstrip('/')
        self.ai_client = OpenAI(api_key=openai_api_key)
        
        self.client_id = client_id or os.getenv("SHOPIFY_CLIENT_ID") or os.getenv("SHOPIFY_API_KEY")
        self.client_secret = client_secret or os.getenv("SHOPIFY_CLIENT_SECRET") or os.getenv("SHOPIFY_SECRET")
        self.access_token = access_token or os.getenv("SHOPIFY_ACCESS_TOKEN")
        
        # Per le API di Shopify, se disponiamo di un access token diretto lo usiamo, 
        # altrimenti se abbiamo la chiave API/Client ID e il secret (shpss_), 
        # configuriamo l'autenticazione HTTP Basic o l'header basato su di essi.
        self.token = self.access_token
        
        # Prepariamo gli headers di autenticazione standard per Shopify Admin API
        self.headers = {
            "Content-Type": "application/json"
        }
        
        if self.token:
            self.headers["X-Shopify-Access-Token"] = self.token
        elif self.client_id and self.client_secret:
            # Se stiamo usando le credenziali API (chiave e segreto), le passiamo come token o autenticazione
            # Nota: se Shopify richiede la chiave API come username e il secret come password per Basic Auth:
            import base64
            auth_string = f"{self.client_id}:{self.client_secret}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            self.headers["Authorization"] = f"Basic {encoded_auth}"

    def get_products(self, limit=20):
        """Recupera l'elenco dei prodotti dal negozio Shopify includendo tutti gli stati."""
        url = f"{self.shop_url}/admin/api/2024-01/products.json?limit={limit}&status=any"
        response = requests.get(url, headers=self.headers)
        
        print(f"[DEBUG SHOPIFY] Status Code Risposta: {response.status_code}")
        print(f"[DEBUG SHOPIFY] Contenuto Risposta: {response.text[:300]}")
        
        if response.status_code == 200:
            return response.json().get("products", [])
        else:
            print(f"[ERRORE] Impossibile recuperare i prodotti: {response.status_code} - {response.text}")
            return []

    def optimize_divise_content(self, title, current_body):
        """Usa l'IA per generare HTML del corpo, Meta Title e Meta Description ottimizzati SEO per le divise."""
        system_prompt = """
Sei un assistente specializzato ed esperto di abbigliamento professionale e divise per sanità, estetica, sala, cucina e hospitality. 
La tua voce è professionale, concreta e rassicurante. Parla come una persona esperta del settore, non come un testo promozionale. 
Il tono è cortese ma diretto, con frasi brevi e utili. Focalizzati su comfort, vestibilità, resistenza ai lavaggi, tessuti, sicurezza, praticità e personalizzazione (valori del made in Italy dal 2007). 
Elimina qualsiasi superlativo inutile, aggettivi in fila o frasi 'da vetrina'.

REGOLE TASSATIVE PER L'OUTPUT:
Devi restituire esclusivamente un oggetto JSON valido (senza blocchi di markdown ```json o altro, solo il testo grezzo JSON) con questa struttura esatta:
{
  "seo_title": "Stringa di massimo 55-60 caratteri, ottimizzata per Google e per il click",
  "seo_description": "Stringa tra i 140 e i 155 caratteri, persuasiva e ricca di valore per i clienti",
  "body_html": "Il codice HTML puro (strutturato con <h2>, <p>, <ul>, <li>, <strong>) con la descrizione dettagliata"
}

Non aggiungere alcun testo prima o dopo il JSON.
"""

        user_prompt = f"""
Ottimizza il seguente prodotto per il nostro e-commerce di divise professionali.
        
Nome Prodotto: {title}
Descrizione Attuale: {current_body}
"""

        try:
            response = self.ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            raw_content = response.choices[0].message.content.strip()
            
            if raw_content.startswith("```"):
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:].strip()
                raw_content = raw_content.rstrip("`").strip()

            data = json.loads(raw_content)
            return data
        except Exception as e:
            print(f"Errore durante la generazione o il parsing JSON dall'IA: {e}")
            return None

    def update_product_seo_and_description(self, product_id, seo_data, tag_to_add="Ottimizzato IA"):
        """Aggiorna su Shopify descrizione HTML, Meta Title, Meta Description e tag."""
        get_url = f"{self.shop_url}/admin/api/2024-01/products/{product_id}.json"
        get_resp = requests.get(get_url, headers=self.headers)
        
        current_tags_str = ""
        if get_resp.status_code == 200:
            product_data = get_resp.json().get("product", {})
            current_tags_str = product_data.get("tags", "")

        tags_list = [t.strip() for t in current_tags_str.split(",")] if current_tags_str else []
        if tag_to_add not in tags_list:
            tags_list.append(tag_to_add)
        
        updated_tags_str = ", ".join(tags_list)

        put_url = f"{self.shop_url}/admin/api/2024-01/products/{product_id}.json"
        payload = {
            "product": {
                "id": product_id,
                "body_html": seo_data.get("body_html"),
                "metafields_global_title_tag": seo_data.get("seo_title"),
                "metafields_global_description_tag": seo_data.get("seo_description"),
                "tags": updated_tags_str
            }
        }
        
        response = requests.put(put_url, json=payload, headers=self.headers)
        
        if response.status_code == 200:
            print(f"[SUCCESSO] Prodotto ID {product_id} ottimizzato con HTML e Meta Tag SEO!")
            return True
        else:
            print(f"[ERRORE] Impossibile aggiornare il prodotto {product_id}: {response.text}")
            return False
