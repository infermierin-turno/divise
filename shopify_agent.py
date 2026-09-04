import os
import requests
from openai import OpenAI
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

class ShopifyCoffeeAgent:
    def __init__(self, shop_url: str, client_id: str, client_secret: str, openai_api_key: str):
        self.shop_url = shop_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.access_token = self._get_access_token()

    def _get_access_token(self) -> str:
        # Se usi un token di accesso diretto o l'autenticazione personalizzata della tua app Shopify
        # Adatta questa chiamata se usi le credenziali OAuth o un token permanente della Custom App.
        auth_url = f"{self.shop_url}/admin/oauth/access_token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        try:
            response = requests.post(auth_url, json=payload)
            if response.status_code == 200:
                return response.json().get("access_token")
        except Exception:
            pass
        # Fallback nel caso in cui client_id/secret siano usati diversamente o sia un token diretto
        return self.client_secret

    def get_products(self, limit=20):
        url = f"{self.shop_url}/admin/api/2024-01/products.json?limit={limit}"
        headers = {"X-Shopify-Access-Token": self.access_token}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("products", [])
        return []

    def optimize_coffee_content(self, title: str, current_body: str) -> dict:
        system_prompt = (
            "Sei un assistente specializzato ed esperto di abbigliamento professionale e divise "
            "per sanità, estetica, sala, cucina e hospitality. La tua voce è professionale, "
            "concreta e rassicurante. Parla come una persona esperta del settore, non come un testo promozionale. "
            "Il tono è cortese ma diretto, con frasi brevi e utili. Focalizzati su comfort, vestibilità, "
            "resistenza ai lavaggi, tessuti, sicurezza, praticità e personalizzazione (valori del made in Italy dal 2007). "
            "Elimina qualsiasi superlativo inutile, aggettivi in fila o frasi 'da vetrina'.\n\n"
            "Restituisci un oggetto JSON valido con esattamente tre chiavi:\n"
            "1. 'seo_title': un titolo ottimizzato per Google (massimo 60 caratteri).\n"
            "2. 'seo_description': una descrizione per i motori di ricerca (compresa tra 140 e 155 caratteri).\n"
            "3. 'body_html': una descrizione del prodotto formattata in HTML pulito, strutturata con paragrafi e punti elenco se utile, che descriva il capo in modo chiaro, tecnico e professionale."
        )

        user_prompt = f"Titolo Prodotto: {title}\n\nDescrizione Attuale:\n{current_body}"

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )

        import json
        try:
            content = json.loads(response.choices[0].message.content)
            return content
        except Exception:
            return {
                "seo_title": title,
                "seo_description": "",
                "body_html": current_body
            }

    def update_product_seo_and_description(self, product_id: str, seo_payload: dict, tag_to_add: str = "Ottimizzato IA"):
        url = f"{self.shop_url}/admin/api/2024-01/products/{product_id}.json"
        headers = {"X-Shopify-Access-Token": self.access_token}

        # Prima recuperiamo i tag attuali per aggiungere quello nuovo senza sovrascrivere gli altri
        get_res = requests.get(url, headers=headers)
        current_tags = ""
        if get_res.status_code == 200:
            prod_data = get_res.json().get("product", {})
            current_tags = prod_data.get("tags", "")

        tags_list = [t.strip() for t in current_tags.split(",")] if current_tags else []
        if tag_to_add not in tags_list:
            tags_list.append(tag_to_add)
        new_tags_str = ", ".join([t for t in tags_list if t])

        data = {
            "product": {
                "id": product_id,
                "body_html": seo_payload.get("body_html"),
                "tags": new_tags_str
            }
        }
        
        # Aggiornamento prodotto principale
        response = requests.put(url, json=data, headers=headers)
        response.raise_for_status()

        # Nota: Per aggiornare Meta Title e Meta Description su Shopify si usano solitamente i metafields o SEO shopify endpoints.
        # Qui integriamo la struttura base già pronta per l'aggiornamento.
        return True
