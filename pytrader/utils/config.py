import os
from dotenv import load_dotenv


class TradeConfig:
    def __init__(self, dot_env_path: str = None):
        if not load_dotenv(dot_env_path):
            raise ValueError(
                f"Unable to load configuration file: ${dot_env_path or '.env'}"
            )

        self.alpaca_key = os.getenv("alpaca_api_key")
        self.alpaca_secret = os.getenv("alpaca_secret_key")
        self.alpaca_paper = os.getenv("alpaca_paper").lower() == "true"
        self.db_creds_path = os.getenv("firebase_creds")
