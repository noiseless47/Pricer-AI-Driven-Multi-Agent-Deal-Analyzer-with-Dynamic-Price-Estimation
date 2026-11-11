import json
import requests
from bs4 import BeautifulSoup
import re

def load_memory(path="memory.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_name(text):
    text = re.sub(r"[^A-Za-z0-9 ]+", " ", text)
    words = text.split()

    # Keep first 5–7 important words (brand + model)
    core = words[:7]
    return " ".join(core)


def search_flipkart(product):
    q = product.replace(" ", "%20")
    url = f"https://www.flipkart.com/search?q={q}"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    item = soup.select_one("a._1fQZEK") or soup.select_one("a.s1Q9rs")
    if not item:
        return None

    link = "https://www.flipkart.com" + item.get("href")
    name = item.text.strip()

    return {"name": name, "url": link}


def search_amazon(product):
    q = product.replace(" ", "+")
    url = f"https://www.amazon.in/s?k={q}"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    item = soup.select_one("div[data-component-type='s-search-result']")
    if not item:
        return None

    link_elem = item.select_one("a.a-link-normal")
    name_elem = item.select_one("span.a-size-medium")

    if not link_elem or not name_elem:
        return None

    link = "https://www.amazon.in" + link_elem.get("href")
    name = name_elem.text.strip()

    return {"name": name, "url": link}


def process_top_item():
    memory = load_memory()
    desc = memory[0]["deal"]["product_description"]

    product = clean_name(desc)
    print("Searching for:", product)

    flip = search_flipkart(product)
    amazon = search_amazon(product)

    return {
        "clean_name": product,
        "flipkart": flip,
        "amazon": amazon
    }


if __name__ == "__main__":
    result = process_top_item()
    print(json.dumps(result, indent=4))
