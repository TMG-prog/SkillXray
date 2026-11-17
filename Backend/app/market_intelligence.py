"""Deterministic labour-market metrics and skill classification."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from math import isfinite
import re
from typing import Iterable, Mapping, TypedDict

PERIOD_DAYS = 30
TREND_PERIODS = 4
RECENCY_DAYS = PERIOD_DAYS * TREND_PERIODS
LOW_CONFIDENCE_MAX_POSTINGS = 99
MEDIUM_CONFIDENCE_MAX_POSTINGS = 499
TREND_RECENT_DAYS = 90
TREND_BASELINE_DAYS = 275
TREND_HISTORY_DAYS = TREND_RECENT_DAYS + TREND_BASELINE_DAYS
MIN_TREND_RECENT_POSTINGS = 10
MIN_TREND_BASELINE_POSTINGS = 20
MIN_SKILL_POSTINGS = 5
TREND_SMOOTHING_ALPHA = 1.0

CORE_MARKET_SKILL = "Core Market Skill"
COMMON_SKILL = "Common Skill"
GROWING_SKILL = "Growing Skill"
EMERGING_SKILL = "Emerging Skill"
NICHE_SKILL = "Niche Skill"
DECLINING_SKILL = "Declining Skill"
STABLE_SKILL = "Stable Skill"


@dataclass(frozen=True)
class SkillMarketMetrics:
    esco_uri: str
    skill_name: str
    posting_count: int
    role_count: int
    frequency: float
    role_penetration: float
    growth_rate: float | None
    recency_score: float
    demand_percentile: float
    commonness_score: float
    classification: str
    confidence: str
    negative_periods: int = 0


class SkillGapReport(TypedDict):
    missing_core: list[dict[str, object]]
    missing_common: list[dict[str, object]]
    missing_emerging: list[dict[str, object]]
    declining_owned_skills: list[dict[str, object]]
    market_alignment_score: float


class SkillEmergence(TypedDict):
    skill_id: str
    esco_uri: str | None
    skill: str
    is_esco: bool
    history: list[float]
    previous_frequency: float
    current_frequency: float
    delta_pp: float
    growth_rate: float
    emergence_score: float
    status: str
    recent_count: int
    baseline_count: int
    recent_postings: int
    baseline_postings: int
    first_seen: bool
    confidence: str
    evidence: str
    sample_postings: list[dict[str, str]]


@dataclass
class _SkillTrendObservation:
    skill: str
    esco_uri: str | None
    is_esco: bool
    recent_jobs: set[str] = field(default_factory=set)
    baseline_jobs: set[str] = field(default_factory=set)
    recent_samples: list[dict[str, str]] = field(default_factory=list)
    baseline_samples: list[dict[str, str]] = field(default_factory=list)


class MarketEmergence(TypedDict):
    role: str
    country: str | None
    recent_window_days: int
    baseline_window_days: int
    recent_window_start: str
    recent_window_end: str
    baseline_window_start: str
    baseline_window_end: str
    minimum_skill_support: int
    minimum_recent_postings: int
    minimum_baseline_postings: int
    data_sufficient: bool
    current_postings: int
    previous_postings: int
    skills: list[SkillEmergence]


_UNMAPPED_TERM_ALIASES = {
    "gen ai": "generative ai llm applications",
    "genai": "generative ai llm applications",
    "generative ai": "generative ai llm applications",
    "generative artificial intelligence": "generative ai llm applications",
    "llm app": "generative ai llm applications",
    "llm apps": "generative ai llm applications",
    "llm application": "generative ai llm applications",
    "llm applications": "generative ai llm applications",
    "large language model app": "generative ai llm applications",
    "large language model apps": "generative ai llm applications",
    "large language model application": "generative ai llm applications",
    "large language model applications": "generative ai llm applications",
}


def canonicalize_unmapped_term(term: str) -> str:
    """Normalize extracted terms and group the known GenAI/LLM application variants."""
    normalized = re.sub(r"[^a-z0-9+#]+", " ", term.casefold()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    canonical = _UNMAPPED_TERM_ALIASES.get(normalized, normalized)
    if canonical == "generative ai llm applications":
        return "Generative AI / LLM Applications"
    return " ".join(word.capitalize() for word in canonical.split())


def _as_datetime(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field} must be a date, datetime, or ISO-8601 string") from exc
    else:
        raise ValueError(f"{field} must be a date, datetime, or ISO-8601 string")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clamp_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def calculate_commonness_score(
    frequency: float,
    penetration: float,
    recency: float,
    growth: float | None,
) -> float:
    """Return a 0-100 score; missing growth is treated as neutral."""
    normalized_growth = 0.5 if growth is None else _clamp_unit((growth + 1.0) / 2.0)
    return 100.0 * (
        0.50 * _clamp_unit(frequency)
        + 0.20 * _clamp_unit(penetration)
        + 0.20 * normalized_growth
        + 0.10 * _clamp_unit(recency)
    )


def classify_skill(metrics: SkillMarketMetrics) -> str:
    """Classify a skill in the specified priority order."""
    if (
        metrics.demand_percentile >= 90
        and metrics.frequency >= 0.50
        and metrics.role_penetration >= 0.40
    ):
        return CORE_MARKET_SKILL
    if metrics.demand_percentile >= 70:
        return COMMON_SKILL
    if metrics.growth_rate is not None and metrics.growth_rate >= 0.20 and metrics.demand_percentile >= 50:
        return GROWING_SKILL
    if (
        metrics.growth_rate is not None
        and metrics.growth_rate >= 0.30
        and metrics.demand_percentile < 50
        and metrics.recency_score >= 0.70
    ):
        return EMERGING_SKILL
    if metrics.demand_percentile < 30 and metrics.role_penetration < 0.20:
        return NICHE_SKILL
    if (
        metrics.growth_rate is not None
        and metrics.growth_rate < 0
        and metrics.negative_periods >= 2
    ):
        return DECLINING_SKILL
    return STABLE_SKILL


def _period_index(posted_at: datetime, reference: datetime) -> int | None:
    age_days = (reference - posted_at).total_seconds() / 86400
    if age_days < 0 or age_days >= RECENCY_DAYS:
        return None
    return TREND_PERIODS - 1 - int(age_days // PERIOD_DAYS)


def compute_emergence_table(
    postings: Iterable[Mapping[str, object]],
    role_family: str,
    reference_date: date | datetime,
    *,
    region: str | None = None,
    limit: int = 10,
) -> MarketEmergence:
    """Compare 90 recent days with the preceding 275 days for one role and region."""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    reference = _as_datetime(reference_date, "reference_date")
    selected_role = role_family.strip().casefold()
    selected_region = region.strip().casefold() if region else None
    recent_start = reference - timedelta(days=TREND_RECENT_DAYS)
    baseline_start = recent_start - timedelta(days=TREND_BASELINE_DAYS)
    recent_postings = 0
    baseline_postings = 0
    observations: dict[str, _SkillTrendObservation] = {}
    seen_jobs: set[str] = set()

    for posting in postings:
        role = str(posting.get("role_family", "")).strip().casefold()
        if role != selected_role:
            continue
        if selected_region is not None:
            posting_region = posting.get("region", posting.get("country"))
            if not isinstance(posting_region, str) or posting_region.strip().casefold() != selected_region:
                continue

        posted_at = _as_datetime(posting.get("posted_date"), "posted_date")
        if posted_at > reference or posted_at < baseline_start:
            continue
        job_id = str(posting.get("job_id", "")).strip()
        if not job_id:
            raise ValueError("each posting must have a non-empty job_id")
        if job_id in seen_jobs:
            raise ValueError(f"duplicate job_id for trend report: {job_id}")
        seen_jobs.add(job_id)
        is_recent = posted_at >= recent_start
        if is_recent:
            recent_postings += 1
        else:
            baseline_postings += 1

        raw_skills = posting.get("esco_skills")
        if not isinstance(raw_skills, (list, tuple)):
            raise ValueError(f"posting {job_id} must have an esco_skills list")
        posting_skills: dict[str, tuple[str, str | None, bool]] = {}
        for skill in raw_skills:
            if not isinstance(skill, Mapping):
                raise ValueError(f"posting {job_id} contains an invalid ESCO skill")
            uri = str(skill.get("esco_uri", "")).strip()
            label = str(skill.get("label", "")).strip()
            if not uri or not label:
                raise ValueError(f"posting {job_id} skills must have an esco_uri and label")
            posting_skills[f"esco:{uri}"] = (label, uri, True)

        raw_unmapped = posting.get("unmapped_skills", [])
        if not isinstance(raw_unmapped, (list, tuple)):
            raise ValueError(f"posting {job_id} must have an unmapped_skills list")
        for raw_term in raw_unmapped:
            if not isinstance(raw_term, str):
                raise ValueError(f"posting {job_id} contains an invalid unmapped skill")
            label = canonicalize_unmapped_term(raw_term)
            if len(label) >= 3:
                term_uri = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")
                posting_skills[f"term:{term_uri}"] = (label, None, False)

        sample = {
            "title": str(posting.get("title", "")).strip(),
            "posted_at": posted_at.date().isoformat(),
            "publisher": str(posting.get("publisher", "")).strip(),
        }
        for skill_id, (label, uri, is_esco) in posting_skills.items():
            observation = observations.setdefault(
                skill_id,
                _SkillTrendObservation(label, uri, is_esco),
            )
            observation.skill = min(
                (observation.skill, label),
                key=lambda value: (value.casefold(), value),
            )
            window_jobs = observation.recent_jobs if is_recent else observation.baseline_jobs
            window_jobs.add(job_id)
            if sample["title"]:
                window_samples = observation.recent_samples if is_recent else observation.baseline_samples
                window_samples.append(sample)

    trends: list[SkillEmergence] = []
    for skill_id, observation in observations.items():
        recent_count = len(observation.recent_jobs)
        baseline_count = len(observation.baseline_jobs)
        if max(recent_count, baseline_count) < MIN_SKILL_POSTINGS:
            continue

        recent_rate = (
            (recent_count + TREND_SMOOTHING_ALPHA)
            / (recent_postings + 2 * TREND_SMOOTHING_ALPHA)
            if recent_postings else 0.0
        )
        baseline_rate = (
            (baseline_count + TREND_SMOOTHING_ALPHA)
            / (baseline_postings + 2 * TREND_SMOOTHING_ALPHA)
            if baseline_postings else 0.0
        )
        current_frequency = 100.0 * recent_rate
        previous_frequency = 100.0 * baseline_rate
        delta_pp = current_frequency - previous_frequency
        growth_rate = recent_rate / baseline_rate - 1.0 if baseline_rate else 0.0
        comparison_supported = (
            recent_postings >= MIN_TREND_RECENT_POSTINGS
            and baseline_postings >= MIN_TREND_BASELINE_POSTINGS
        )

        if recent_count >= MIN_SKILL_POSTINGS and current_frequency >= 50.0:
            status = "core"
        elif (
            comparison_supported
            and recent_count >= MIN_SKILL_POSTINGS
            and baseline_count < MIN_SKILL_POSTINGS
            and delta_pp >= 2.0
            and growth_rate >= 0.25
        ):
            status = "rising"
        elif (
            comparison_supported
            and recent_count >= MIN_SKILL_POSTINGS
            and baseline_count >= MIN_SKILL_POSTINGS
            and delta_pp >= 2.0
            and growth_rate >= 0.25
        ):
            status = "rising"
        elif (
            comparison_supported
            and baseline_count >= MIN_SKILL_POSTINGS
            and delta_pp <= -2.0
            and growth_rate <= -0.25
        ):
            status = "declining"
        else:
            status = "stable"

        confidence = (
            "high" if recent_postings >= 100 and baseline_postings >= 100
            else "medium" if comparison_supported
            else "low"
        )
        current_samples = sorted(
            observation.recent_samples,
            key=lambda item: (item["posted_at"], item["title"]),
            reverse=True,
        )
        samples = current_samples or sorted(
            observation.baseline_samples,
            key=lambda item: (item["posted_at"], item["title"]),
            reverse=True,
        )
        sample_postings = samples[:3]
        evidence = (
            f"{recent_count}/{recent_postings} recent postings ({current_frequency:.1f}%) "
            f"vs {baseline_count}/{baseline_postings} baseline postings ({previous_frequency:.1f}%)."
        )
        if not comparison_supported:
            evidence += (
                f" Trend comparison requires at least {MIN_TREND_RECENT_POSTINGS} recent and "
                f"{MIN_TREND_BASELINE_POSTINGS} baseline postings."
            )
        if not current_samples and sample_postings:
            evidence += " Samples are from the baseline window."

        trends.append({
            "skill_id": skill_id,
            "esco_uri": observation.esco_uri,
            "skill": observation.skill,
            "is_esco": observation.is_esco,
            "history": [round(previous_frequency, 2), round(current_frequency, 2)],
            "previous_frequency": round(previous_frequency, 2),
            "current_frequency": round(current_frequency, 2),
            "delta_pp": round(delta_pp, 2),
            "growth_rate": round(growth_rate, 3),
            "emergence_score": round(max(0.0, delta_pp) * recent_rate, 3),
            "status": status,
            "recent_count": recent_count,
            "baseline_count": baseline_count,
            "recent_postings": recent_postings,
            "baseline_postings": baseline_postings,
            "first_seen": baseline_count == 0 and recent_count > 0,
            "confidence": confidence,
            "evidence": evidence,
            "sample_postings": sample_postings,
        })

    status_order = {"core": 0, "rising": 1, "stable": 2, "declining": 3}
    trends.sort(key=lambda item: (
        status_order[item["status"]],
        -item["current_frequency"] if item["status"] == "core" else (
            -item["delta_pp"] if item["status"] == "rising" else (
                -item["current_frequency"] if item["status"] == "stable" else item["delta_pp"]
            )
        ),
        item["skill_id"],
    ))
    return {
        "role": role_family,
        "country": selected_region,
        "recent_window_days": TREND_RECENT_DAYS,
        "baseline_window_days": TREND_BASELINE_DAYS,
        "recent_window_start": recent_start.date().isoformat(),
        "recent_window_end": reference.date().isoformat(),
        "baseline_window_start": baseline_start.date().isoformat(),
        "baseline_window_end": recent_start.date().isoformat(),
        "minimum_skill_support": MIN_SKILL_POSTINGS,
        "minimum_recent_postings": MIN_TREND_RECENT_POSTINGS,
        "minimum_baseline_postings": MIN_TREND_BASELINE_POSTINGS,
        "data_sufficient": (
            recent_postings >= MIN_TREND_RECENT_POSTINGS
            and baseline_postings >= MIN_TREND_BASELINE_POSTINGS
        ),
        "current_postings": recent_postings,
        "previous_postings": baseline_postings,
        "skills": trends[:limit],
    }


def compute_skill_metrics(
    postings: Iterable[Mapping[str, object]],
    reference_date: date | datetime,
    *,
    region: str | None = None,
) -> dict[str, SkillMarketMetrics]:
    """Compute URI-keyed demand metrics from job postings with linked ESCO skills.

    Growth compares the most recent 30-day skill frequency with the preceding
    30 days. ``negative_periods`` counts downward frequency changes across the
    four most recent 30-day periods; declining classification requires at
    least two such changes. Recency is the mean linear decay over 120 days.

    If the previous period has postings but no instances of a skill, positive
    current demand is represented as 100% growth. Growth is unknown when the
    previous period contains no postings.
    """
    reference = _as_datetime(reference_date, "reference_date")
    selected_region = region.strip().casefold() if region else None
    jobs: list[tuple[str, datetime, str, set[str]]] = []
    seen_job_ids: set[str] = set()
    labels: dict[str, set[str]] = {}

    for posting in postings:
        job_id = str(posting.get("job_id", "")).strip()
        if not job_id:
            raise ValueError("each posting must have a non-empty job_id")
        if job_id in seen_job_ids:
            raise ValueError(f"duplicate job_id: {job_id}")
        seen_job_ids.add(job_id)

        if selected_region is not None:
            posting_region = posting.get("region", posting.get("country"))
            if not isinstance(posting_region, str) or posting_region.strip().casefold() != selected_region:
                continue

        posted_at = _as_datetime(posting.get("posted_date"), "posted_date")
        if posted_at > reference:
            continue

        role_family = str(posting.get("role_family", "")).strip().casefold()
        raw_skills = posting.get("esco_skills")
        if not isinstance(raw_skills, (list, tuple)):
            raise ValueError(f"posting {job_id} must have an esco_skills list")

        skill_uris: set[str] = set()
        for skill in raw_skills:
            if not isinstance(skill, Mapping):
                raise ValueError(f"posting {job_id} contains an invalid ESCO skill")
            uri = str(skill.get("esco_uri", "")).strip()
            label = str(skill.get("label", "")).strip()
            if not uri or not label:
                raise ValueError(f"posting {job_id} skills must have an esco_uri and label")
            skill_uris.add(uri)
            labels.setdefault(uri, set()).add(label)

        jobs.append((job_id, posted_at, role_family, skill_uris))

    total_postings = len(jobs)
    all_roles = {role for _, _, role, _ in jobs if role}
    skill_jobs: dict[str, set[str]] = {}
    skill_roles: dict[str, set[str]] = {}
    skill_dates: dict[str, list[datetime]] = {}
    skill_period_counts: dict[str, list[int]] = {}
    period_posting_counts = [0] * TREND_PERIODS

    for job_id, posted_at, role_family, skill_uris in jobs:
        period = _period_index(posted_at, reference)
        if period is not None:
            period_posting_counts[period] += 1
        for uri in skill_uris:
            skill_jobs.setdefault(uri, set()).add(job_id)
            if role_family:
                skill_roles.setdefault(uri, set()).add(role_family)
            skill_dates.setdefault(uri, []).append(posted_at)
            counts = skill_period_counts.setdefault(uri, [0] * TREND_PERIODS)
            if period is not None:
                counts[period] += 1

    frequencies = {
        uri: len(job_ids) / total_postings if total_postings else 0.0
        for uri, job_ids in skill_jobs.items()
    }
    confidence = (
        "low" if total_postings <= LOW_CONFIDENCE_MAX_POSTINGS
        else "medium" if total_postings <= MEDIUM_CONFIDENCE_MAX_POSTINGS
        else "high"
    )
    provisional: dict[str, dict[str, object]] = {}

    for uri, job_ids in skill_jobs.items():
        counts = skill_period_counts[uri]
        period_frequencies = [
            counts[i] / period_posting_counts[i] if period_posting_counts[i] else None
            for i in range(TREND_PERIODS)
        ]
        previous = period_frequencies[-2]
        current = period_frequencies[-1]
        if previous is None or current is None:
            growth_rate = None
        elif previous == 0:
            growth_rate = 1.0 if current > 0 else 0.0
        else:
            growth_rate = current / previous - 1.0

        negative_periods = sum(
            1
            for earlier, later in zip(period_frequencies, period_frequencies[1:])
            if earlier is not None and later is not None and later < earlier
        )
        recency_score = sum(
            max(0.0, 1.0 - max(0.0, (reference - posted_at).total_seconds() / 86400) / RECENCY_DAYS)
            for posted_at in skill_dates[uri]
        ) / len(skill_dates[uri])
        role_count = len(skill_roles.get(uri, set()))
        role_penetration = role_count / len(all_roles) if all_roles else 0.0
        provisional[uri] = {
            "skill_name": min(labels.get(uri, {uri}), key=lambda label: (label.casefold(), label)),
            "posting_count": len(job_ids),
            "role_count": role_count,
            "frequency": frequencies[uri],
            "role_penetration": role_penetration,
            "growth_rate": growth_rate,
            "recency_score": recency_score,
            "negative_periods": negative_periods,
        }

    demand_values = list(frequencies.values())
    metrics_by_uri: dict[str, SkillMarketMetrics] = {}
    for uri, values in provisional.items():
        percentile = (
            100.0 * sum(value <= frequencies[uri] for value in demand_values) / len(demand_values)
            if demand_values else 0.0
        )
        growth_rate = values["growth_rate"]
        commonness = calculate_commonness_score(
            float(values["frequency"]),
            float(values["role_penetration"]),
            float(values["recency_score"]),
            growth_rate if isinstance(growth_rate, (int, float)) else None,
        )
        metrics = SkillMarketMetrics(
            esco_uri=uri,
            skill_name=str(values["skill_name"]),
            posting_count=int(values["posting_count"]),
            role_count=int(values["role_count"]),
            frequency=float(values["frequency"]),
            role_penetration=float(values["role_penetration"]),
            growth_rate=float(growth_rate) if isinstance(growth_rate, (int, float)) else None,
            recency_score=float(values["recency_score"]),
            demand_percentile=percentile,
            commonness_score=commonness,
            classification=STABLE_SKILL,
            confidence=confidence,
            negative_periods=int(values["negative_periods"]),
        )
        metrics_by_uri[uri] = SkillMarketMetrics(
            **{**asdict(metrics), "classification": classify_skill(metrics)}
        )

    return {uri: metrics_by_uri[uri] for uri in sorted(metrics_by_uri)}


def detect_skill_gaps(
    candidate_skills: Iterable[Mapping[str, str]],
    market_metrics: Mapping[str, SkillMarketMetrics],
) -> SkillGapReport:
    """Summarize market-priority gaps using ESCO URI membership only."""
    candidate_uris = {
        str(skill.get("esco_uri", "")).strip()
        for skill in candidate_skills
        if str(skill.get("esco_uri", "")).strip()
    }
    missing_core: list[SkillMarketMetrics] = []
    missing_common: list[SkillMarketMetrics] = []
    missing_emerging: list[SkillMarketMetrics] = []
    declining_owned: list[SkillMarketMetrics] = []

    for uri, metrics in market_metrics.items():
        if uri != metrics.esco_uri:
            raise ValueError(f"market metrics key does not match ESCO URI: {uri}")
        owned = uri in candidate_uris
        if owned and metrics.classification == DECLINING_SKILL:
            declining_owned.append(metrics)
        elif not owned:
            if metrics.classification == CORE_MARKET_SKILL:
                missing_core.append(metrics)
            elif metrics.classification == COMMON_SKILL:
                missing_common.append(metrics)
            elif metrics.classification == EMERGING_SKILL:
                missing_emerging.append(metrics)

    ordering = lambda metric: (-metric.commonness_score, metric.esco_uri)
    missing_core.sort(key=ordering)
    missing_common.sort(key=ordering)
    missing_emerging.sort(key=ordering)
    declining_owned.sort(key=ordering)

    total_weight = sum(metric.commonness_score for metric in market_metrics.values())
    alignment = (
        100.0 * sum(
            metric.commonness_score
            for uri, metric in market_metrics.items()
            if uri in candidate_uris
        ) / total_weight
        if total_weight and isfinite(total_weight)
        else 0.0
    )
    return {
        "missing_core": [asdict(metric) for metric in missing_core],
        "missing_common": [asdict(metric) for metric in missing_common],
        "missing_emerging": [asdict(metric) for metric in missing_emerging],
        "declining_owned_skills": [asdict(metric) for metric in declining_owned],
        "market_alignment_score": round(alignment, 2),
    }
