import os
from typing import Optional
from dotenv import load_dotenv
from ...domain.models import Listing
from ...domain.ports import ClassifierPort


PROMPT = (
    "You filter government procurement opportunities for a custom software development company.\n"
    "Return 'YES' if the work likely involves: software/app/web/mobile development, modernization, systems integration, APIs, data platforms/ETL/analytics/AI, cloud engineering, cybersecurity software, DevOps/SRE, or IT program management with software deliverables.\n"
    "Return 'NO' for: physical goods/hardware-only, construction/facilities, janitorial, printing, furniture, uniforms, fleet/vehicles, food, or purely non-software staffing. If uncertain but plausibly software-related, prefer YES.\n"
    "Respond with exactly YES or NO.\n"
)


class OpenAIClassifier(ClassifierPort):
    def __init__(self) -> None:
        load_dotenv()
        # Lazy import to avoid hard dependency if not used
        from openai import OpenAI  # type: ignore

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set")
        self._client = OpenAI(api_key=api_key)
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def is_relevant(self, listing: Listing) -> bool:
        title = listing.title.strip()
        desc = (listing.description or "").strip()
        user = f"Title: {title}\nDescription: {desc}"
        try:
            # Use responses API; if not available in installed version, fall back to chat.completions
            try:
                result = self._client.responses.create(
                    model=self._model,
                    input=[
                        {"role": "system", "content": PROMPT},
                        {"role": "user", "content": user},
                    ],
                )
                text: Optional[str] = None
                if result and result.output and len(result.output) > 0:
                    text = result.output[0].content[0].text  # type: ignore[attr-defined]
                answer = (text or "").strip().upper()
            except Exception:
                chat = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": PROMPT},
                        {"role": "user", "content": user},
                    ],
                    temperature=0,
                    max_tokens=3,
                )
                answer = (chat.choices[0].message.content or "").strip().upper()
            return answer.startswith("Y")
        except Exception as e:
            print(f"[classifier] OpenAI error: {e}")
            # Fail open: consider relevant to avoid missing opportunities
            return True


