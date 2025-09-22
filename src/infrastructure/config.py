import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    base_url: str = os.getenv("BASE_URL", "https://www.emarketplace.state.pa.us/Procurement.aspx")
    check_interval_minutes: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
    reset_state_on_start: bool = os.getenv("RESET_STATE_ON_START", "false").lower() in {"1", "true", "yes"}


settings = Settings()
