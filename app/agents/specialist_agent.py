import modal
from app.agents.agent import Agent


class SpecialistAgent(Agent):
    """
    Agent that calls your fine-tuned LLM running remotely on Modal
    to estimate the price of an item.  
    Now fully adapted for INR (₹) predictions.
    """

    name = "Specialist Agent"
    color = Agent.RED

    def __init__(self):
        """
        Initialize modal remote class instance
        """
        self.log("Specialist Agent is initializing - connecting to modal")
        Pricer = modal.Cls.from_name("pricer-service", "Pricer")
        self.pricer = Pricer()
        self.log("Specialist Agent is ready")

    def price(self, description: str) -> float:
        """
        Make a remote call to the fine-tuned model  
        Returns estimated price **in INR (₹)** as a float
        """
        self.log("Specialist Agent is calling remote fine-tuned model")
        result = self.pricer.price.remote(description)

        # Log in INR
        self.log(f"Specialist Agent completed - predicting ₹{result:.2f}")

        return result
