import os
import json
from typing import Optional, List
from openai import OpenAI
from app.agents.deals import ScrapedDeal, DealSelection, Deal
from app.agents.agent import Agent


class ScannerAgent(Agent):

    MODEL = "llama3.2"

    SYSTEM_PROMPT = """You identify and summarize..."""

    USER_PROMPT_PREFIX = """Respond with the most promising..."""

    USER_PROMPT_SUFFIX = "\n\nStrictly respond in JSON and include exactly 5 deals, no more."

    name = "Scanner Agent"
    color = Agent.CYAN

    def __init__(self):
        self.log("Scanner Agent is initializing")
        self.openai = OpenAI()
        self.log("Scanner Agent is ready")

    def fetch_deals(self, memory) -> List[ScrapedDeal]:
        self.log("Scanner Agent is about to fetch deals from RSS feed")
        urls = [opp.deal.url for opp in memory]
        scraped = ScrapedDeal.fetch()
        result = [s for s in scraped if s.url not in urls]
        self.log(f"Scanner Agent received {len(result)} deals not already scraped")
        return result

    def make_user_prompt(self, scraped) -> str:
        user_prompt = self.USER_PROMPT_PREFIX
        user_prompt += '\n\n'.join([scrape.describe() for scrape in scraped])
        user_prompt += self.USER_PROMPT_SUFFIX
        return user_prompt

    def scan(self, memory: List[str]=[]) -> Optional[DealSelection]:
        scraped = self.fetch_deals(memory)
        if scraped:
            user_prompt = self.make_user_prompt(scraped)
            self.log("Scanner Agent is calling OpenAI using Structured Output")

            result = self.openai.beta.chat.completions.parse(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=DealSelection
            )

            result = result.choices[0].message.parsed
            result.deals = [deal for deal in result.deals if deal.price > 0]

            # attach domain from ScrapedDeal to Deal
            for d in result.deals:
                for s in scraped:
                    if s.url == d.url:
                        d.domain = s.category

            self.log(f"Scanner Agent received {len(result.deals)} selected deals with price>0")
            return result

        return None
