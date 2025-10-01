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
        print(f"[sync] Found {len(current)} IT listings.")

        previous = self.state_repo.load_last_snapshot()
        print(f"[sync] Loaded previous snapshot with {len(previous)} listings.")

        prev_by_id = self._index_by_id(previous)
        # Build seen sets to skip anything we've already crawled
        seen_ids = {p.id for p in previous}
        seen_urls = {p.detail_url for p in previous}

        # Only process truly new items; skip enrichment/classification for anything already seen by id or url
        to_enrich: List[Listing] = [l for l in current if (l.id not in seen_ids and l.detail_url not in seen_urls)]
        print(f"[sync] New items to process: {len(to_enrich)}; skipping {len(current) - len(to_enrich)} already-seen.")

        enriched_new = [self.scraper.enrich_description(l) for l in to_enrich]
        print("[sync] Enrichment complete.")

        # Classify and send only new URLs
        to_send: List[Listing] = enriched_new
        if enriched_new and self.classifier is not None:
            print("[sync] Classifying new listings for relevance…")
            filtered: List[Listing] = []
            for l in enriched_new:
                try:
                    if await self.classifier.is_relevant(l):
                        filtered.append(l)
                except Exception as e:
                    print(f"[sync] Classifier error for {l.id}: {e}")
            print(f"[sync] {len(filtered)}/{len(enriched_new)} new listings deemed relevant.")
            to_send = filtered

        if to_send:
            print("[sync] Sending relevant listings to notifier…")
            await self.notifier.send_listings(to_send)

        # Persist snapshot as union of previous and current; reuse previous descriptions for already-seen items
        latest_by_id = {l.id: l for l in previous}
        # First, ensure all current items are present; reuse prev.description when not enriched
        enriched_by_id = {l.id: l for l in enriched_new}
        for cur in current:
            if cur.id in enriched_by_id:
                latest_by_id[cur.id] = enriched_by_id[cur.id]
            else:
                prev = prev_by_id.get(cur.id)
                latest_by_id[cur.id] = Listing(
                    id=cur.id,
                    title=cur.title,
                    agency=cur.agency,
                    category=cur.category,
                    status=cur.status,
                    detail_url=cur.detail_url,
                    description=(prev.description if prev else None),
                )
        print("[sync] Saving snapshot…")
        self.state_repo.save_snapshot(list(latest_by_id.values()))
        print("[sync] Snapshot saved.")
