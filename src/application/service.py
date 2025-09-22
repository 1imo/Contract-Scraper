from typing import List, Dict
from ..domain.models import Listing
from ..domain.ports import ListingsScraperPort, NotifierPort, StateRepositoryPort, ClassifierPort


class SyncService:
    def __init__(self, scraper: ListingsScraperPort, notifier: NotifierPort, state_repo: StateRepositoryPort, classifier: ClassifierPort | None = None) -> None:
        self.scraper = scraper
        self.notifier = notifier
        self.state_repo = state_repo
        self.classifier = classifier

    def _index_by_id(self, listings: List[Listing]) -> Dict[str, Listing]:
        return {l.id: l for l in listings}

    async def sync_once(self) -> None:
        print("[sync] Fetching current IT listings…")
        current = self.scraper.fetch_it_listings()
        print(f"[sync] Found {len(current)} IT listings. Enriching descriptions…")
        enriched = [self.scraper.enrich_description(l) for l in current]
        print("[sync] Enrichment complete.")

        previous = self.state_repo.load_last_snapshot()
        print(f"[sync] Loaded previous snapshot with {len(previous)} listings.")

        prev_by_id = self._index_by_id(previous)
        cur_by_id = self._index_by_id(enriched)

        changed: List[Listing] = []
        for listing in enriched:
            prev = prev_by_id.get(listing.id)
            if prev is None or (
                prev.title != listing.title or prev.status != listing.status or prev.description != listing.description
            ):
                changed.append(listing)

        print(f"[sync] Detected {len(changed)} new/updated listings.")
        if changed:
            to_send = changed
            if self.classifier is not None:
                print("[sync] Classifying changed listings for relevance…")
                filtered: List[Listing] = []
                for l in changed:
                    try:
                        if await self.classifier.is_relevant(l):
                            filtered.append(l)
                    except Exception as e:
                        print(f"[sync] Classifier error for {l.id}: {e}")
                print(f"[sync] {len(filtered)}/{len(changed)} listings deemed relevant.")
                to_send = filtered
            if to_send:
                print("[sync] Sending relevant listings to notifier…")
                await self.notifier.send_listings(to_send)
            print("[sync] Saving snapshot of all listings…")
            self.state_repo.save_snapshot(enriched)
            print("[sync] Snapshot saved.")
        else:
            print("[sync] No changes to send.")
