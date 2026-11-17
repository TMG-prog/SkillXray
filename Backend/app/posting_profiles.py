"""Build role profiles from recently ingested Supabase postings."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import pandas as pd

from .market_intelligence import (
    MarketEmergence,
    SkillMarketMetrics,
    compute_emergence_table,
    compute_skill_metrics,
)

log = logging.getLogger("skillxray.posting_profiles")

RECENCY_DAYS = 30
MARKET_HISTORY_DAYS = 365
MARKET_METRICS_DAYS = 120
MIN_DESCRIPTION_CHARS = 400
MIN_ROLE_POSTINGS = 30
MIN_ROLE_FREQ = 0.20
MIN_ROLE_DOCS = 3
MAX_ROLE_SKILLS = 40
MIN_MEDIAN_SKILLS = 8.5  # Half the notebook's static median of 17 skills per posting.
PAGE_SIZE = 1000


def build_database_profile(engine, role: str, postings: list[dict]) -> tuple[pd.DataFrame, dict]:
    """Apply the notebook's extraction and role-frequency rules to one role's postings."""
    ids = [str(posting["id"]) for posting in postings]
    texts = [str(posting["description"]) for posting in postings]
    info = {
        "role": role,
        "source": "database",
        "n_postings": len(ids),
        "country": _country_summary(postings),
        "reason": "",
    }

    if len(ids) < MIN_ROLE_POSTINGS:
        return pd.DataFrame(), {**info, "reason": f"only {len(ids)} recent postings (< {MIN_ROLE_POSTINGS})"}

    spans = engine.extract_docs(texts, ids, engine.EXTRACTION_CFG)
    if spans is None or len(spans) == 0:
        return pd.DataFrame(), {**info, "reason": "no skills extracted from recent postings"}

    skills = engine.collapse_to_skills(engine.standardise_spans(spans))
    if skills is None or len(skills) == 0:
        return pd.DataFrame(), {**info, "reason": "no skills linked from recent postings"}

    skills = skills.assign(doc_id=skills["doc_id"].astype(str))
    median_skills = float(
        skills.groupby("doc_id")["esco_uri"].nunique().reindex(ids).fillna(0).median()
    )
    info["median_skills"] = median_skills

    counts = skills.groupby("esco_uri")["doc_id"].nunique().rename("n_docs")
    metadata = skills.drop_duplicates("esco_uri").set_index("esco_uri")[["esco_label", "in_esco"]]
    profile = pd.concat([counts, metadata], axis=1)
    profile["freq"] = profile["n_docs"] / len(ids)
    profile = profile[(profile["freq"] >= MIN_ROLE_FREQ) & (profile["n_docs"] >= MIN_ROLE_DOCS)]
    profile = profile.sort_values(["freq", "n_docs"], ascending=False).head(MAX_ROLE_SKILLS)
    if profile.empty:
        return pd.DataFrame(), {**info, "reason": "no skill reached the notebook frequency threshold"}

    profile["weight"] = profile["freq"] / profile["freq"].sum()
    profile["n_postings"] = len(ids)
    profile.insert(0, "role", role)
    profile = profile.rename_axis("esco_uri").reset_index()
    profile = engine._apply_blocklist(profile)
    if profile.empty:
        return pd.DataFrame(), {**info, "reason": "no requirements remain after the blocklist"}
    profile["weight"] = profile["weight"] / profile["weight"].sum()

    if median_skills < MIN_MEDIAN_SKILLS:
        return profile.reset_index(drop=True), {
            **info,
            "reason": (
                f"median {median_skills:.1f} skills per posting is below "
                f"the notebook quality threshold of {MIN_MEDIAN_SKILLS:.1f}"
            ),
        }

    return profile.reset_index(drop=True), info


class DatabaseProfileProvider:
    """Read recent postings once, then derive each role profile on first use."""

    def __init__(self, client, engine, *, now: datetime | None = None, country: str | None = None):
        self.engine = engine
        self.now = _parse_datetime(now) or datetime.now(timezone.utc)
        self.country = (country or "").strip().lower() or None
        self.market_postings = self._load_postings(client)
        profile_cutoff = self.now - timedelta(days=RECENCY_DAYS)
        self.postings = {
            role: [
                posting for posting in postings
                if (_parse_datetime(posting.get("posted_at"))
                    or _parse_datetime(posting.get("fetched_at"))
                    or self.now) >= profile_cutoff
            ]
            for role, postings in self.market_postings.items()
        }
        self._profile_cache: dict[str, tuple[pd.DataFrame, dict] | None] = {}
        self._fallback_reasons: dict[str, str] = {}
        self._market_metrics_cache: dict[str, SkillMarketMetrics] | None = None
        self._market_role_uris: dict[str, set[str]] = {}
        self._market_emergence_cache: dict[str, MarketEmergence] = {}
        self._market_postings_cache: list[dict] = []

    def available_roles(self) -> list[str]:
        return sorted(
            role for role, postings in self.postings.items()
            if len(postings) >= MIN_ROLE_POSTINGS
        )

    def fallback_reason(self, role: str) -> str | None:
        return self._fallback_reasons.get(role)

    def market_metrics_for_role(self, role: str) -> dict[str, SkillMarketMetrics]:
        """Return market-wide metrics restricted to skills observed for one role."""
        metrics = self._market_metrics()
        role_uris = self._market_role_uris.get(role.strip().lower(), set())
        return {uri: metrics[uri] for uri in sorted(role_uris) if uri in metrics}

    def market_emergence_for_role(self, role: str) -> MarketEmergence:
        """Return recent posting-frequency trends scoped to a single role."""
        self._market_metrics()
        role_key = role.strip().lower()
        if role_key not in self._market_emergence_cache:
            self._market_emergence_cache[role_key] = compute_emergence_table(
                self._market_postings_cache,
                role,
                self.now,
                region=self.country,
            )
        return self._market_emergence_cache[role_key]

    def skill_cooccurrence_for_role(
        self,
        role: str,
        candidate_uris: set[str],
        gap_uris: set[str],
    ) -> dict[str, dict[str, object]]:
        """Measure gap-skill frequency among role postings that list any owned skill."""
        self._market_metrics()
        role_postings = [
            posting for posting in self._market_postings_cache
            if posting["role_family"] == role.strip().lower()
        ]
        posting_skills = {
            str(posting["job_id"]): {
                str(skill["esco_uri"]) for skill in posting["esco_skills"]
            }
            for posting in role_postings
        }
        personalized_postings = [
            posting for posting in role_postings
            if posting_skills[str(posting["job_id"])] & candidate_uris
        ]
        evidence_postings = personalized_postings or role_postings
        personalized = bool(personalized_postings)
        sample_size = len(evidence_postings)
        role_size = len(role_postings)
        result: dict[str, dict[str, object]] = {}

        for uri in gap_uris:
            posting_count = sum(uri in posting_skills[str(posting["job_id"])] for posting in evidence_postings)
            role_count = sum(uri in posting_skills[str(posting["job_id"])] for posting in role_postings)
            frequency = posting_count / sample_size if sample_size else None
            baseline_frequency = role_count / role_size if role_size else None
            if sample_size:
                evidence = (
                    f"{posting_count} of {sample_size} role postings that also list at least one skill "
                    f"from your resume ({frequency:.0%}) also list this skill; "
                    if personalized
                    else f"{posting_count} of {sample_size} recent postings for this role "
                    f"({frequency:.0%}) list this skill; "
                )
                if baseline_frequency is not None:
                    evidence += (
                        f"the role-wide rate is {baseline_frequency:.0%} "
                        f"({role_count} of {role_size} postings)."
                    )
            else:
                evidence = "No recent postings with linked skills are available for this role."
            result[uri] = {
                "sample_size": sample_size,
                "posting_count": posting_count,
                "frequency": round(frequency, 3) if frequency is not None else None,
                "baseline_frequency": round(baseline_frequency, 3) if baseline_frequency is not None else None,
                "personalized": personalized,
                "evidence": evidence,
            }
        return result

    def _market_metrics(self) -> dict[str, SkillMarketMetrics]:
        if self._market_metrics_cache is None:
            postings = [
                posting
                for role_postings in self.market_postings.values()
                for posting in role_postings
                if _parse_datetime(posting.get("posted_at")) is not None
            ]
            if not postings:
                self._market_metrics_cache = {}
                return self._market_metrics_cache

            ids = [str(posting["id"]) for posting in postings]
            texts = [str(posting["description"]) for posting in postings]
            spans = self.engine.extract_docs(texts, ids, self.engine.EXTRACTION_CFG)
            standardized = (
                self.engine.standardise_spans(spans)
                if spans is not None and len(spans)
                else pd.DataFrame()
            )
            skills = (
                self.engine.collapse_to_skills(standardized)
                if len(standardized)
                else pd.DataFrame()
            )

            skills_by_job: dict[str, dict[str, str]] = {}
            if skills is not None and len(skills):
                for row in skills.itertuples(index=False):
                    skills_by_job.setdefault(str(row.doc_id), {})[str(row.esco_uri)] = str(row.esco_label)

            unmapped_by_job: dict[str, set[str]] = {}
            unmapped_reasons = {"ambiguous", "below_threshold", "no_lexical_support"}
            if {"doc_id", "skill_text", "status", "reason"}.issubset(standardized.columns):
                unmapped = standardized[
                    standardized["status"].ne("accepted")
                    & standardized["reason"].isin(unmapped_reasons)
                ]
                for row in unmapped.itertuples(index=False):
                    term = str(row.skill_text).strip()
                    if term:
                        unmapped_by_job.setdefault(str(row.doc_id), set()).add(term)

            market_postings = []
            for posting in postings:
                job_id = str(posting["id"])
                role = str(posting.get("role_key") or "").strip().lower()
                esco_skills = [
                    {"esco_uri": uri, "label": label}
                    for uri, label in sorted(skills_by_job.get(job_id, {}).items())
                ]
                self._market_role_uris.setdefault(role, set()).update(
                    skill["esco_uri"] for skill in esco_skills
                )
                market_postings.append({
                    "job_id": job_id,
                    "posted_date": posting["posted_at"],
                    "role_family": role,
                    "region": posting.get("country"),
                    "esco_skills": esco_skills,
                    "unmapped_skills": sorted(unmapped_by_job.get(job_id, set())),
                    "title": str(posting.get("title") or "").strip(),
                    "publisher": str(posting.get("publisher") or "").strip(),
                })

            self._market_postings_cache = market_postings
            metrics_cutoff = self.now - timedelta(days=MARKET_METRICS_DAYS)
            recent_market_postings = [
                posting for posting in market_postings
                if _parse_datetime(posting["posted_date"]) >= metrics_cutoff
            ]
            self._market_metrics_cache = compute_skill_metrics(
                recent_market_postings,
                self.now,
                region=self.country,
            )
        return self._market_metrics_cache

    def get_profile(self, role: str) -> tuple[pd.DataFrame, dict] | None:
        if role not in self._profile_cache:
            postings = self.postings.get(role, [])
            if len(postings) < MIN_ROLE_POSTINGS:
                reason = f"only {len(postings)} recent JSearch postings (< {MIN_ROLE_POSTINGS})"
                self._fallback_reasons[role] = reason
                self._profile_cache[role] = None
            else:
                profile, info = build_database_profile(self.engine, role, postings)
                if info["reason"]:
                    self._fallback_reasons[role] = info["reason"]
                    self._profile_cache[role] = None
                else:
                    self._profile_cache[role] = (profile, info)
        return self._profile_cache[role]

    def _load_postings(self, client) -> dict[str, list[dict]]:
        cutoff = self.now - timedelta(days=MARKET_HISTORY_DAYS)
        rows = []
        offset = 0
        while True:
            query = (
                client.table("job_postings")
                .select(
                    "id,role_key,description,title,posted_at,fetched_at,country,publisher,dedupe_key"
                )
                .gte("posted_at", cutoff.isoformat())
            )
            if self.country:
                query = query.eq("country", self.country)
            batch = query.order("fetched_at", desc=True).range(
                offset, offset + PAGE_SIZE - 1
            ).execute().data
            rows.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        by_role: dict[str, dict[str, dict]] = {}
        for row in rows:
            description = str(row.get("description") or "").strip()
            role = str(row.get("role_key") or "").strip().lower()
            if not role or len(description) < MIN_DESCRIPTION_CHARS:
                continue
            posted_at = _parse_datetime(row.get("posted_at"))
            if posted_at is None or posted_at < cutoff or posted_at > self.now:
                continue
            posting = {**row, "description": description}
            country = str(row.get("country") or "").strip().lower()
            dedupe_key = _trend_dedupe_key(posting)
            role_postings = by_role.setdefault(role, {})
            dedupe_key = f"{country}:{dedupe_key}"
            existing = role_postings.get(dedupe_key)
            if existing is None or posted_at > _parse_datetime(existing["posted_at"]):
                role_postings[dedupe_key] = posting

        deduplicated_by_role = {
            role: sorted(
                postings.values(),
                key=lambda posting: _parse_datetime(posting["posted_at"]),
                reverse=True,
            )
            for role, postings in by_role.items()
        }

        log.info(
            "Loaded %d deduplicated Supabase postings over %d days for %d roles%s",
            sum(map(len, deduplicated_by_role.values())),
            MARKET_HISTORY_DAYS,
            len(deduplicated_by_role),
            f" in {self.country}" if self.country else "",
        )
        return deduplicated_by_role


def provider_from_environment(engine) -> DatabaseProfileProvider | None:
    url = os.getenv("SUPABASE_URL", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not service_key:
        log.warning(
            "Database-backed profiles are disabled: set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in the backend environment."
        )
        return None

    from supabase import create_client

    client = create_client(url, service_key)
    return DatabaseProfileProvider(client, engine, country=os.getenv("JSEARCH_COUNTRY"))


def _parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _trend_dedupe_key(posting: dict) -> str:
    title = str(posting.get("title") or "").casefold()
    description = str(posting.get("description") or "").casefold()
    normalized = unicodedata.normalize("NFKC", f"{title}\n{description}")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[^\w+#. ]+", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized:
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    stored_key = str(posting.get("dedupe_key") or "").strip()
    return stored_key or str(posting.get("id") or "")


def _country_summary(postings: list[dict]) -> str | None:
    countries = sorted({str(row["country"]).lower() for row in postings if row.get("country")})
    return countries[0] if len(countries) == 1 else (", ".join(countries) if countries else None)
