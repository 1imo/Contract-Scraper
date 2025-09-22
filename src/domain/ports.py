from abc import ABC, abstractmethod
from typing import List
from .models import Listing


class ListingsScraperPort(ABC):
    @abstractmethod
    def fetch_it_listings(self) -> List[Listing]:
        ...

    @abstractmethod
    def enrich_description(self, listing: Listing) -> Listing:
        ...


class NotifierPort(ABC):
    @abstractmethod
    async def send_listings(self, listings: List[Listing]) -> None:
        ...


class StateRepositoryPort(ABC):
    @abstractmethod
    def load_last_snapshot(self) -> List[Listing]:
        ...

    @abstractmethod
    def save_snapshot(self, listings: List[Listing]) -> None:
        ...


class ClassifierPort(ABC):
    @abstractmethod
    async def is_relevant(self, listing: Listing) -> bool:
        ...
