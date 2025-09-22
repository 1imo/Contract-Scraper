import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.adapters.scraper.emarketplace_scraper import EMarketplaceScraper
from src.adapters.notifier.discord_notifier import DiscordNotifier
from src.adapters.state.json_state_repo import JsonStateRepository
from src.adapters.classifier.openai_classifier import OpenAIClassifier
from src.application.service import SyncService
from src.infrastructure.config import settings
import os


async def run_once():
    scraper = EMarketplaceScraper()
    notifier = DiscordNotifier()
    state_repo = JsonStateRepository()
    classifier = None
    try:
        classifier = OpenAIClassifier()
        print("[main] OpenAI classifier initialized.")
    except Exception as e:
        print(f"[main] OpenAI classifier not available: {e}")
    if settings.reset_state_on_start:
        try:
            state_path = os.path.join(os.path.dirname(__file__), "..", "data", "state.json")
            state_path = os.path.abspath(state_path)
            if os.path.exists(state_path):
                print(f"[main] RESET_STATE_ON_START is true; removing {state_path}")
                os.remove(state_path)
        except Exception as e:
            print(f"[main] Failed to reset state: {e}")
    service = SyncService(scraper, notifier, state_repo, classifier)
    await service.sync_once()


async def main():
    await run_once()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_once, "interval", minutes=settings.check_interval_minutes, id="sync")
    scheduler.start()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
