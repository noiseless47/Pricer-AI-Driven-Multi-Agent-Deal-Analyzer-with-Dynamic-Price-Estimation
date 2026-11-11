from typing import Optional, List
from app.agents.agent import Agent
from app.agents.deals import Deal, Opportunity
from app.agents.scanner_agent import ScannerAgent
from app.agents.ensemble_agent import EnsembleAgent
from app.agents.messaging_agent import MessagingAgent
import random


class PlanningAgent(Agent):

    name = "Planning Agent"
    color = Agent.GREEN

    DEAL_THRESHOLD = 50  # INR

    def __init__(self, collection):
        self.log("Planning Agent is initializing")
        self.scanner = ScannerAgent()
        self.ensemble = EnsembleAgent(collection)
        self.messenger = MessagingAgent()
        self.log("Planning Agent is ready")

    def run(self, deal: Deal) -> Opportunity:
        """
        Estimate INR price & compute INR discount.
        """
        self.log("Planning Agent is pricing up a potential deal")
    
        # 1. Get estimate from ensemble (USD)
        estimate_usd = self.ensemble.price(deal.product_description)
    
        # 2. Convert USD → INR with correct rate
        estimate = estimate_usd * 83
    
        # 3. Compute discount in INR
        discount = estimate - deal.price
    
        self.log(f"Planning Agent has processed a deal with estimate ₹{estimate:.2f} and discount ₹{discount:.2f}")
    
        # 4. Return Opportunity (INR values)
        return Opportunity(
            deal=deal,
            estimate=estimate,
            discount=discount
        )



    def plan(self, memory: List[str] = []) -> Optional[Opportunity]:

        self.log("Planning Agent is kicking off a run")

        selection = self.scanner.scan(memory=memory)
        if selection:
            opportunities = [self.run(d) for d in selection.deals[:5]]

            # Rank highest discount
            opportunities.sort(key=lambda opp: opp.discount, reverse=True)
            best = opportunities[0]

            self.log(f"Planning Agent has identified the best deal has discount ₹{best.discount:.2f}")

            # Send alert if threshold crossed
            if best.discount > self.DEAL_THRESHOLD:
                self.messenger.alert(best)

            self.log("Planning Agent has completed a run")
            return best

        return None
