from pydantic import BaseModel
from typing import List, Dict, Self
from bs4 import BeautifulSoup
import re
import feedparser
from tqdm import tqdm
import requests
import time
import logging

# -----------------------------------------------------------
# INDIA RSS DEAL FEEDS
# -----------------------------------------------------------
feeds = [
    "https://www.desidime.com/deals.rss",
    "https://www.desidime.com/stores/amazon-india.rss",
    "https://www.desidime.com/stores/flipkart.rss",
    "https://www.desidime.com/stores/reliance-digital.rss",
    "https://www.desidime.com/stores/tata-cliq.rss",
    "https://www.desidime.com/stores/croma.rss",
    "https://www.desidime.com/stores/ajio.rss",
    "https://www.desidime.com/stores/myntra.rss",
    "https://www.desidime.com/stores/nykaa.rss",

    "https://www.reddit.com/r/indiandeals/.rss",
    "https://www.reddit.com/r/IndianGaming/.rss",
    "https://www.reddit.com/r/buildapcsalesindia/.rss",
]

logger = logging.getLogger("ScrapedDeal")
logger.setLevel(logging.INFO)


# -----------------------------------------------------------
# DOMAIN DETECTOR (Category Classifier)
# -----------------------------------------------------------
def classify_domain(text: str) -> str:
    t = text.lower()

    if any(x in t for x in ["iphone", "mobile", "smartphone", "android", "galaxy"]):
        return "Mobiles"
    if any(x in t for x in ["laptop", "macbook", "notebook", "ultrabook"]):
        return "Laptops"
    if any(x in t for x in ["headphone", "earphone", "earbud", "airpods"]):
        return "Headphones"
    if any(x in t for x in ["gaming", "ps5", "xbox", "controller", "gpu", "rtx"]):
        return "Gaming"
    if any(x in t for x in ["jeans", "shirt", "dress", "tshirt", "apparel"]):
        return "Clothing"
    if any(x in t for x in ["watch", "smartwatch"]):
        return "Smartwatches"
    if any(x in t for x in ["tv", "television"]):
        return "TVs"
    if any(x in t for x in ["camera", "dslr"]):
        return "Cameras"
    if any(x in t for x in ["home", "kitchen", "cookware", "appliance"]):
        return "Home & Kitchen"

    return "Others"


# -----------------------------------------------------------
# CLEAN HTML SNIPPET FROM RSS
# -----------------------------------------------------------
def extract(html_snippet: str) -> str:
    soup = BeautifulSoup(html_snippet, 'html.parser')
    snippet_div = soup.find('div', class_='snippet summary')

    if snippet_div:
        description = snippet_div.get_text(strip=True)
        description = BeautifulSoup(description, 'html.parser').get_text()
        description = re.sub('<[^<]+?>', '', description)
        result = description.strip()
    else:
        result = html_snippet

    return result.replace('\n', ' ')


# -----------------------------------------------------------
# EXTRACT INDIAN PRICES FROM TEXT
# -----------------------------------------------------------
def extract_indian_price(text: str):
    patterns = [
        r"₹\s*([\d,]+)",
        r"Rs\.?\s*([\d,]+)",
        r"INR\s*([\d,]+)"
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


# -----------------------------------------------------------
# SCRAPED DEAL CLASS
# -----------------------------------------------------------
class ScrapedDeal:
    category: str
    title: str
    summary: str
    url: str
    details: str
    features: str
    raw_price: float | None

    def __init__(self, entry: Dict[str, str]):
        self.title = entry.get("title", "").strip()
        self.summary = extract(entry.get("summary", "") or entry.get("description", ""))

        if "links" in entry:
            self.url = entry["links"][0].get("href", "")
        else:
            self.url = entry.get("link", "")

        self.details = ""
        self.features = ""
        self.raw_price = None

        # CATEGORY ASSIGNMENT BASED ON TITLE
        self.category = classify_domain(self.title + " " + self.summary)

        try:
            headers = {
                "User-Agent":
                    "Mozilla/5.0"
            }
            r = requests.get(self.url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.content, "html.parser")

            candidates = [
                soup.find("div", {"class": "deal-desc"}),
                soup.find("div", {"class": "content-section"}),
                soup.find("div", {"class": "description"}),
                soup.find("div", {"id": "content"}),
                soup.find("article"),
                soup.find("div", {"class": "post-content"}),
                soup.find("div", {"class": "entry-content"}),
            ]

            node = next((x for x in candidates if x), None)

            if node:
                content = node.get_text(" ", strip=True)
            else:
                meta = soup.find("meta", {"name": "description"}) or \
                       soup.find("meta", {"property": "og:description"})

                content = meta.get("content", "") if meta else self.summary

            content = re.sub(r"\s+", " ", content).strip()

            if "Features" in content:
                parts = re.split(r"\bFeatures\b", content, maxsplit=1)
                self.details = parts[0].strip()
                self.features = parts[1].strip()
            else:
                self.details = content
                self.features = ""

            self.raw_price = (
                    extract_indian_price(self.details)
                    or extract_indian_price(self.summary)
                    or None
            )

        except Exception:
            self.details = self.summary
            self.features = ""
            self.raw_price = extract_indian_price(self.summary)

    def __repr__(self):
        return f"<{self.title}>"

    def describe(self):
        return (
            f"Title: {self.title}\n"
            f"Category: {self.category}\n"
            f"Raw Price: {self.raw_price}\n"
            f"Details: {self.details}\n"
            f"Features: {self.features}\n"
            f"URL: {self.url}"
        )


# -----------------------------------------------------------
# FETCH ALL DEALS
# -----------------------------------------------------------
    @classmethod
    def fetch(cls, show_progress: bool = False) -> List[Self]:
        deals = []
        feed_iter = tqdm(feeds) if show_progress else feeds

        for feed_url in feed_iter:
            try:
                feed = feedparser.parse(feed_url)
            except:
                continue

            for entry in feed.entries[:10]:
                try:
                    deals.append(cls(entry))
                except:
                    pass

                time.sleep(0.4)

        return deals


# -----------------------------------------------------------
# DATA MODELS
# -----------------------------------------------------------
class Deal(BaseModel):
    product_description: str
    price: float
    url: str
    domain: str = "Others"   # NEW FIELD


class DealSelection(BaseModel):
    deals: List[Deal]


class Opportunity(BaseModel):
    deal: Deal
    estimate: float
    discount: float
