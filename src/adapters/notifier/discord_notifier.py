import asyncio
import os
from typing import List, Optional
import discord
from dotenv import load_dotenv
from ...domain.models import Listing

# Ensure .env is loaded even if infrastructure.config isn't imported yet
load_dotenv()


class DiscordNotifier:
    def __init__(self) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        self.client = discord.Client(intents=intents)
        self._ready = asyncio.Event()
        self._token: Optional[str] = None
        self._guild_id: Optional[int] = None
        self._channel_id: Optional[int] = None
        self._client_task: Optional[asyncio.Task] = None

        @self.client.event
        async def on_ready():
            print(f"[discord] Logged in as {self.client.user}")
            print("[discord] Guilds:")
            for g in self.client.guilds:
                print(f"  - {g.name} ({g.id})")
                for c in g.text_channels:
                    print(f"     # {c.name} ({c.id})")
            self._ready.set()

    def _load_env(self) -> None:
        if self._token is None:
            self._token = os.getenv("DISCORD_TOKEN")
        if self._guild_id is None:
            try:
                self._guild_id = int(os.getenv("DISCORD_GUILD_ID", "0"))
            except ValueError:
                self._guild_id = 0
        if self._channel_id is None:
            try:
                self._channel_id = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
            except ValueError:
                self._channel_id = 0
        masked = (self._token[:4] + "…") if self._token else None
        print(f"[discord] Env loaded: token={masked}, guild_id={self._guild_id}, channel_id={self._channel_id}")

    async def _ensure_started(self) -> None:
        self._load_env()
        if not self._token or not self._guild_id or not self._channel_id:
            raise RuntimeError("DISCORD_TOKEN, DISCORD_GUILD_ID, DISCORD_CHANNEL_ID must be set")
        if self._client_task is None or self._client_task.done():
            print("[discord] Starting client in background…")
            self._client_task = asyncio.create_task(self.client.start(self._token))
        await self._ready.wait()

    async def _send_message(self, content: str) -> None:
        await self._ready.wait()
        try:
            guild = self.client.get_guild(self._guild_id) if self._guild_id else None
            if guild is None:
                print(f"[discord] get_guild({self._guild_id}) returned None; trying fetch_guild…")
                guild = await self.client.fetch_guild(self._guild_id)
            channel = guild.get_channel(self._channel_id) if guild else None
            if channel is None:
                print(f"[discord] channel not found in cache; trying fetch_channel({self._channel_id})…")
                channel = await self.client.fetch_channel(self._channel_id)
            # Split into chunks of <= 1900 characters to stay under Discord's 2000 limit
            chunks = self._split_into_chunks(content, 1900)
            total = len(chunks)
            for idx, chunk in enumerate(chunks, 1):
                prefix = "" if total == 1 else f"(part {idx}/{total})\n"
                body = prefix + chunk
                print(f"[discord] Sending message to #{getattr(channel, 'name', '?')} ({self._channel_id})… chunk {idx}/{total} size={len(body)}")
                await channel.send(body)
            print("[discord] Message(s) sent.")
        except Exception as e:
            print(f"[discord] Error sending message: {e}")
            raise

    def _format_listing_header(self, l: Listing) -> str:
        return (
            f"**{l.title}** (ID: {l.id})\n"
            f"Agency: {l.agency} | Status: {l.status}\n"
            f"<{l.detail_url}>"
        )

    def _format_listing_description(self, l: Listing) -> str:
        return (l.description or "").strip()

    def _split_into_chunks(self, text: str, limit: int) -> list[str]:
        chunks: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            # try to split at a newline before the limit
            cut = remaining.rfind("\n", 0, limit)
            if cut == -1 or cut < limit * 0.6:  # if no good break, hard cut
                cut = limit
            chunks.append(remaining[:cut])
            remaining = remaining[cut:].lstrip("\n")
        return chunks

    async def send_listings(self, listings: List[Listing]) -> None:
        print(f"[discord] Preparing to send {len(listings)} listings…")
        await self._ensure_started()
        try:
            for i, l in enumerate(listings, 1):
                print(f"[discord] ({i}/{len(listings)}) sending {l.id}…")
                # Send header once
                await self._send_message(self._format_listing_header(l))
                # Then chunk only the description
                desc = self._format_listing_description(l)
                if desc:
                    print(f"[discord] Sending description chunks for {l.id}…")
                    await self._send_message(desc)
        finally:
            print("[discord] Closing client…")
            try:
                await self.client.close()
            except Exception as e:
                print(f"[discord] Error closing client: {e}")
            await asyncio.sleep(0)
            if self._client_task and not self._client_task.done():
                self._client_task.cancel()
                self._client_task = None
