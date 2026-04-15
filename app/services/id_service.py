from __future__ import annotations

import re
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.domain import PublicIdCounter


class PublicIdService:
    def __init__(self, db: Session):
        self.db = db

    def next_id(self, model: type, prefix: str, year: int | None = None) -> str:
        year = year or date.today().year
        while True:
            counter = self.db.scalar(
                select(PublicIdCounter)
                .where(PublicIdCounter.scope == prefix, PublicIdCounter.year == year)
                .with_for_update()
            )
            if counter is None:
                counter = PublicIdCounter(scope=prefix, year=year, last_value=0)
                self.db.add(counter)
                self.db.flush()

            counter.last_value += 1
            candidate = f"{prefix}-{year}-{counter.last_value:04d}"

            exists = self.db.scalar(select(func.count()).select_from(model).where(model.display_id == candidate)) or 0
            if exists == 0:
                return candidate

    def next_deal_id(self, model: type, client_name: str, submitted_on: date | None = None) -> str:
        submitted_on = submitted_on or date.today()
        year_full = submitted_on.year
        year_short = year_full % 100
        abbrev = self._brand_abbreviation(client_name)
        scope = f"DEAL:{abbrev}"
        while True:
            counter = self.db.scalar(
                select(PublicIdCounter)
                .where(PublicIdCounter.scope == scope, PublicIdCounter.year == year_full)
                .with_for_update()
            )
            if counter is None:
                counter = PublicIdCounter(scope=scope, year=year_full, last_value=0)
                self.db.add(counter)
                self.db.flush()

            counter.last_value += 1
            candidate = f"{abbrev}-{year_short:02d}-{counter.last_value:03d}"
            exists = self.db.scalar(select(func.count()).select_from(model).where(model.display_id == candidate)) or 0
            if exists == 0:
                return candidate

    def next_campaign_id(self, model: type, brand_code: str, yy: int, product_code: str) -> str:
        year_key = 2000 + yy
        scope = f"CAMP:{brand_code}:{product_code}"
        while True:
            counter = self.db.scalar(
                select(PublicIdCounter)
                .where(PublicIdCounter.scope == scope, PublicIdCounter.year == year_key)
                .with_for_update()
            )
            if counter is None:
                counter = PublicIdCounter(scope=scope, year=year_key, last_value=0)
                self.db.add(counter)
                self.db.flush()

            counter.last_value += 1
            if counter.last_value > 99:
                raise ValueError(f"Campaign sequence overflow for {brand_code}-{yy:02d}-{product_code}")

            candidate = f"{brand_code}-{yy:02d}-{product_code}-{counter.last_value:02d}"
            exists = self.db.scalar(select(func.count()).select_from(model).where(model.display_id == candidate)) or 0
            if exists == 0:
                return candidate

    def _brand_abbreviation(self, client_name: str) -> str:
        ticker_map = {
            "microsoft": "MSFT",
        }
        cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", (client_name or "")).strip()
        if not cleaned:
            return "DEAL"

        compact = re.sub(r"\s+", " ", cleaned).strip().lower()
        if compact in ticker_map:
            return ticker_map[compact]

        tokens = [t for t in compact.split(" ") if t]
        stop_words = {
            "communications",
            "communication",
            "networks",
            "network",
            "technologies",
            "technology",
            "systems",
            "system",
            "solutions",
            "solution",
            "group",
            "global",
            "limited",
            "ltd",
            "inc",
            "corp",
            "corporation",
            "plc",
            "llc",
            "co",
            "company",
        }
        meaningful = [t for t in tokens if t not in stop_words]
        base = meaningful[0] if meaningful else tokens[0]
        base = re.sub(r"[^a-z]", "", base)
        if not base:
            return "DEAL"

        if len(base) <= 4:
            return base.upper().ljust(4, "X")

        vowels = set("aeiou")
        first = base[0]
        tail_vowel = base[-1] if base[-1] in vowels else ""
        middle = base[1:-1]

        if first in vowels:
            consonants = [ch for ch in base[1:] if ch not in vowels]
            followed_by_vowel = [
                base[i]
                for i in range(1, len(base) - 1)
                if base[i] not in vowels and base[i + 1] in vowels
            ]
            ordered: list[str] = []
            if consonants:
                ordered.append(consonants[0])  # preserve first consonant after leading vowel
            for ch in followed_by_vowel:
                if ch not in ordered:
                    ordered.append(ch)
            for ch in consonants:
                if ch not in ordered:
                    ordered.append(ch)
            selected = [first] + ordered[:3]
            if len(selected) < 4 and tail_vowel:
                selected.append(tail_vowel)
            return "".join(selected[:4]).upper().ljust(4, "X")

        compressed = first + "".join(ch for ch in middle if ch not in vowels) + (tail_vowel or base[-1])
        return compressed[:4].upper().ljust(4, "X")
