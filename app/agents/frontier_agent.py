import os
import re
import math
import json
from typing import List, Dict
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from datasets import load_dataset


class FrontierAgent:

    name = "Frontier Agent"
    color = "blue"

    def __init__(self, collection):
        print("Initializing Frontier Agent")

        # Read .env style local OpenAI variables
        base_url = "http://localhost:11434/v1"
        api_key = "ollama"

        if base_url is None:
            raise ValueError("OPENAI_BASE_URL not set in environment")
        if api_key is None:
            raise ValueError("OPENAI_API_KEY not set in environment")

        # This points to your local LLaMA 3.2 via Ollama
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        
        # Correct model identifier for Ollama OpenAI API mode
        self.MODEL = "llama3.2"

        print(f"Frontier Agent is using LOCAL model: {self.MODEL}")
        self.collection = collection
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        print("Frontier Agent ready")

    def make_context(self, similars: List[str], prices: List[float]) -> str:
        msg = "To provide some context, here are some other items similar to the one you need to estimate.\n\n"
        for s, p in zip(similars, prices):
            msg += f"Product:\n{s}\nPrice is ${p:.2f}\n\n"
        return msg

    def messages_for(self, description: str, similars: List[str], prices: List[float]):
        system = "You estimate prices of items. Reply only with the price, no explanation."
        user = self.make_context(similars, prices)
        user += f"And now the question:\n\nHow much does this cost?\n\n{description}"

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": "Price is $"}
        ]

    def find_similars(self, description: str):
        vector = self.model.encode([description])
        results = self.collection.query(
            query_embeddings=vector.astype(float).tolist(),
            n_results=5
        )
        docs = results["documents"][0]
        prices = [m["price"] for m in results["metadatas"][0]]
        return docs, prices

    def get_price(self, s):
        s = s.replace("$", "").replace(",", "")
        m = re.search(r"[-+]?\d*\.\d+|\d+", s)
        return float(m.group()) if m else 0.0

    def price(self, description: str) -> float:
        docs, doc_prices = self.find_similars(description)

        response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=self.messages_for(description, docs, doc_prices),
            seed=42,
            max_tokens=5
        )

        reply = response.choices[0].message.content
        price = self.get_price(reply)

        print(f"Predicted price = ${price:.2f}")
        return price
