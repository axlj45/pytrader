import os
from dotenv import load_dotenv


class TradeConfig:
    def __init__(self, dot_env_path: str = None):
        if not load_dotenv(dot_env_path):
            raise ValueError(f"Unable to load configuration file: {dot_env_path or '.env'}")

        self.alpaca_key = os.getenv("alpaca_api_key")
        self.alpaca_secret = os.getenv("alpaca_secret_key")
        self.alpaca_paper = self._strtobool(os.getenv("alpaca_paper"))
        self.db_creds_path = os.getenv("firebase_creds")
        self.max_single_symbol = float(os.getenv("max_single_symbol") or 0.5)
        self.max_portfolio_usage = float(os.getenv("max_portfolio_usage") or 1)
        self.rsi_timeout_days = int(os.getenv("rsi_timeout_days") or 10)
        self.use_margin = self._strtobool(os.getenv("use_margin"))
        self.rsi_send_gchat = self._strtobool(os.getenv("rsi_send_gchat"))
        self.rsi_gchat_webhook = os.getenv("rsi_gchat_webhook")

    def _strtobool(self, val: str, default=False) -> bool:
        """
        Convert a string representation of truth to true or false.
        True values are 'y', 'yes', 't', 'true', 'on', and '1';
        False valuesare 'n', 'no', 'f', 'false', 'off', and '0'.
        Empty/blank/none values resolve to false unless otherwise specified.
        """

        if not self._has_value(val):
            return default

        val = val.lower()
        if val in ("y", "yes", "t", "true", "on", "1"):
            return True
        elif val in ("n", "no", "f", "false", "off", "0"):
            return False
        else:
            return default

    def _has_value(self, val: str):
        return bool(val and not val.isspace())
