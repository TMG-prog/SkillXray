"""Adapter from the notebook-derived v2 scorer to the mobile API contract."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd

from . import config as C
from .evidence import contextualize_evidence
from .learning_catalog import published_resources
from .market_intelligence import SkillMarketMetrics, detect_skill_gaps
from .matching import NOTEBOOK_ROLE_ALIASES, load_aliases, load_prerequisites
from .pipeline import RoleNotFound

LEARNING_RESOURCES = (
    (("python",), "Python for Everybody Specialization", "Coursera · University of Michigan",
     "https://www.coursera.org/specializations/python"),
    (("sql", "database"), "SQL for Data Science", "Coursera · University of California, Davis",
     "https://www.coursera.org/learn/sql-for-data-science"),
    (("docker",), "Docker for the Absolute Beginner", "KodeKloud",
     "https://kodekloud.com/courses/docker-for-the-absolute-beginner-course/"),
    (("kubernetes",), "Certified Kubernetes Application Developer (CKAD)", "Linux Foundation",
     "https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/"),
    (("terraform",), "Terraform Associate learning path", "HashiCorp",
     "https://developer.hashicorp.com/terraform/tutorials/certification-003"),
    (("aws", "amazon web services"), "AWS Cloud Practitioner Essentials", "AWS Skill Builder",
     "https://skillbuilder.aws/learn"),
    (("azure",), "Azure Fundamentals learning path", "Microsoft Learn",
     "https://learn.microsoft.com/training/paths/azure-fundamentals-describe-cloud-concepts/"),
    (("google cloud", "gcp"), "Google Cloud learning paths", "Google Cloud Skills Boost",
     "https://www.cloudskillsboost.google/paths"),
    (("project management",), "Google Project Management Professional Certificate", "Coursera · Google",
     "https://www.coursera.org/professional-certificates/google-project-management"),
    (("data analytics", "data analysis"), "Google Data Analytics Professional Certificate", "Coursera · Google",
     "https://www.coursera.org/professional-certificates/google-data-analytics"),
    (("machine learning", "artificial intelligence", "deep learning"),
     "Machine Learning Specialization", "Coursera · DeepLearning.AI and Stanford",
     "https://www.coursera.org/specializations/machine-learning-introduction"),
)


class NotebookPipeline:
    def __init__(
        self,
        engine,
        prerequisites: dict[str, list[str]] | None = None,
        role_aliases: dict[str, str] | None = None,
    ):
        self.engine = engine
        self.prerequisites = prerequisites or {}
        self.role_aliases = {
            str(alias).strip().lower(): str(target).strip().lower()
            for alias, target in {**NOTEBOOK_ROLE_ALIASES, **(role_aliases or {})}.items()
        }

    @classmethod
    def load(cls) -> "NotebookPipeline":
        backend_dir = Path(__file__).resolve().parents[1]
        backend_path = str(backend_dir)
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        os.environ.setdefault("SKILLXRAY_DIR", str(C.ARTIFACTS))
        engine = importlib.import_module("skillxray")
        from .posting_profiles import provider_from_environment

        engine.set_profile_provider(provider_from_environment(engine))
        role_aliases = load_aliases(C.ARTIFACTS / "results" / "role_aliases.json")
        prerequisites = load_prerequisites(C.ARTIFACTS / "results" / "skill_prerequisites.json")
        return cls(engine, prerequisites, role_aliases)

    def roles(self) -> dict:
        return {"posting_roles": self.engine.available_roles(), "esco_fallback": False}

    def career_paths(self) -> list[dict]:
        paths = []
        for role in self.engine.available_roles():
            profile, _ = self.engine.get_profile(role)
            requirements = []
            for row in profile.itertuples(index=False):
                requirements.append({
                    "skill": str(row.esco_label),
                    "uri": str(row.esco_uri),
                    "frequency": _optional_number(getattr(row, "freq", None)),
                })
            paths.append({"role": str(role), "requirements": requirements})
        return paths

    def analyze(self, text: str, role: str, role_id: str | None = None) -> dict:
        del role_id
        roles = {str(name).strip().lower(): str(name) for name in self.engine.available_roles()}
        role_key = (role or "").strip().lower()
        canonical_role = roles.get(role_key)
        if canonical_role is None:
            canonical_role = roles.get(self.role_aliases.get(role_key, ""))
        if canonical_role is None:
            raise RoleNotFound(role)

        resume_text = text[:C.MAX_TEXT_CHARS]
        result = self.engine.score_cv(resume_text, canonical_role)
        profile = self.engine.get_profile(canonical_role)[0]
        profile_rows = {
            str(row.esco_uri): row._asdict()
            for row in profile.itertuples(index=False)
        }
        table = result["table"].sort_values("weight", ascending=False, kind="stable")
        requirements = []
        for row in table.itertuples(index=False):
            profile_row = profile_rows.get(str(row.esco_uri))
            if profile_row is None:
                raise ValueError(f"Notebook scorer returned an unknown role requirement URI: {row.esco_uri}")
            frequency = _optional_number(profile_row.get("freq"))
            requirements.append({
                "skill": str(row.esco_label),
                "uri": str(profile_row["esco_uri"]),
                "weight": round(float(row.weight), 4),
                "credit": 1.0 if bool(row.covered) else 0.0,
                "frequency": frequency,
                "reason": str(row.reason),
                "evidence": str(row.closest_evidence),
                "cv_evidence": contextualize_evidence(
                    resume_text,
                    str(getattr(row, "cv_evidence", "")),
                ),
                "cv_highlight": str(getattr(row, "cv_highlight", "")),
                "gap_confidence": round(float(row.gap_confidence), 2),
            })

        covered = [skill for skill in requirements if skill["credit"] == 1.0]
        gaps = [skill for skill in requirements if skill["credit"] == 0.0]
        profile_info = result["profile"]
        warnings = []
        if profile_info.get("reason"):
            warnings.append(f"Using the static role profile: {profile_info['reason']}.")
        if len(result.get("extracted_skills", [])) < 5:
            warnings.append(
                "Very few skills were found in this resume. If it is a scanned or image-heavy PDF, "
                "try a text-based PDF or DOCX."
            )

        provider = getattr(self.engine, "_PROFILE_PROVIDER", None)
        market_intelligence = None
        market_emergence = None
        hiring_evidence = {}
        if provider is not None and hasattr(provider, "market_metrics_for_role"):
            role_market_metrics: dict[str, SkillMarketMetrics] = provider.market_metrics_for_role(canonical_role)
            market_intelligence = detect_skill_gaps(
                [
                    {"esco_uri": skill.get("uri", ""), "label": skill.get("skill", "")}
                    for skill in result.get("extracted_skills", [])
                ],
                role_market_metrics,
            )
        if provider is not None and hasattr(provider, "skill_cooccurrence_for_role"):
            candidate_uris = {
                str(skill.get("uri", "")).strip()
                for skill in result.get("extracted_skills", [])
                if str(skill.get("uri", "")).strip()
            }
            hiring_evidence = provider.skill_cooccurrence_for_role(
                canonical_role,
                candidate_uris,
                {item["uri"] for item in gaps},
            )
        if provider is not None and hasattr(provider, "market_emergence_for_role"):
            market_emergence = provider.market_emergence_for_role(canonical_role)

        for item in requirements:
            item["hiring_evidence"] = hiring_evidence.get(item["uri"])
        skill_edges = self._skill_relationship_edges(profile)
        learning_plan = self._learning_plan(profile, requirements, skill_edges, hiring_evidence)
        marginal_gains = {item["uri"]: item["marginal_gain_pp"] for item in learning_plan}
        for item in requirements:
            item["marginal_gain_pp"] = marginal_gains.get(item["uri"], 0.0)

        return {
            "role": canonical_role,
            "profile_source": profile_info["source"],
            "method": "v22_match_v2",
            "readiness": round(float(result["readiness"]) * 100, 1),
            "n_required": len(requirements),
            "n_covered": len(covered),
            "covered": covered,
            "gaps": gaps,
            "skill_relationships": self._skill_relationships(profile, skill_edges),
            "learning_plan": learning_plan,
            "extracted_skills": result["extracted_skills"],
            "warnings": warnings,
            "timings_ms": result["timings_ms"],
            "market_delta": self._market_delta(requirements),
            "market_intelligence": market_intelligence,
            "market_emergence": market_emergence,
        }

    def _skill_relationship_edges(self, profile: pd.DataFrame) -> list[tuple[str, str, str]]:
        uris = set(profile["esco_uri"].astype(str))
        edges: dict[tuple[str, str], str] = {}
        for skill_uri, required_uris in self.prerequisites.items():
            if skill_uri in uris:
                for prerequisite_uri in required_uris:
                    if prerequisite_uri in uris and prerequisite_uri != skill_uri:
                        edges[(prerequisite_uri, skill_uri)] = "prerequisite"

        graph = getattr(self.engine, "ESCO_GRAPH", None)
        if graph is not None:
            for child_uri in uris:
                for parent_uri in graph["parents"].get(child_uri, ()):
                    if parent_uri in uris and parent_uri != child_uri:
                        edges.setdefault((parent_uri, child_uri), "broader")
            for skill_uri in uris:
                for related_uri in graph["related"].get(skill_uri, ()):
                    if related_uri in uris and skill_uri < related_uri:
                        edges.setdefault((skill_uri, related_uri), "related")

        priority = {"prerequisite": 0, "broader": 1, "related": 2}
        return [
            (source, target, relationship)
            for (source, target), relationship in sorted(
                edges.items(),
                key=lambda item: (priority[item[1]], item[0][0], item[0][1]),
            )[:40]
        ]

    def _skill_relationships(
        self,
        profile: pd.DataFrame,
        edges: list[tuple[str, str, str]] | None = None,
    ) -> list[dict]:
        labels = dict(zip(profile["esco_uri"].astype(str), profile["esco_label"].astype(str)))
        return [
            {"source": labels[source], "target": labels[target], "type": relationship}
            for source, target, relationship in edges or self._skill_relationship_edges(profile)
        ]

    def _learning_plan(
        self,
        profile: pd.DataFrame,
        requirements: list[dict],
        edges: list[tuple[str, str, str]],
        hiring_evidence: dict[str, dict[str, object]],
    ) -> list[dict]:
        if not requirements:
            return []

        catalog = published_resources()
        resources = LEARNING_RESOURCES if catalog is None else catalog
        labels = dict(zip(profile["esco_uri"].astype(str), profile["esco_label"].astype(str)))
        requirements_by_uri = {item["uri"]: item for item in requirements}
        profile_uris = set(requirements_by_uri)
        gap_uris = {item["uri"] for item in requirements if item["credit"] == 0}
        satisfied = {item["uri"] for item in requirements if item["credit"] > 0}
        total_weight = sum(float(item["weight"]) for item in requirements)
        dependencies: dict[str, set[str]] = {uri: set() for uri in gap_uris}
        cluster_neighbours: dict[str, set[str]] = {uri: set() for uri in profile_uris}

        for source, target, relationship in edges:
            if source in profile_uris and target in profile_uris:
                cluster_neighbours[source].add(target)
                cluster_neighbours[target].add(source)
                if (
                    source in profile_uris
                    and target in gap_uris
                    and relationship == "prerequisite"
                ):
                    dependencies[target].add(source)

        graph = getattr(self.engine, "ESCO_GRAPH", None)
        if graph is not None:
            related = graph.get("related", {})
            parents = graph.get("parents", {})
            for uri in profile_uris:
                cluster_neighbours[uri].update(set(related.get(uri, ())) & profile_uris)
                for other in profile_uris - {uri}:
                    if set(parents.get(uri, ())) & set(parents.get(other, ())):
                        cluster_neighbours[uri].add(other)

        descendants = getattr(self.engine, "DESC", None)
        if not isinstance(descendants, dict):
            descendants = _build_descendants(graph, self.engine)

        plan = []
        remaining = set(gap_uris)
        learned_by: dict[str, str] = {}
        while remaining:
            ready = [
                uri for uri in remaining
                if not (dependencies[uri] & remaining)
            ]
            if not ready:
                ready = list(remaining)

            def projected_gain(uri: str) -> tuple[float, set[str]]:
                newly_satisfied = {
                    required_uri
                    for required_uri in requirements_by_uri
                    if required_uri not in satisfied
                    and (
                        required_uri == uri
                        or uri in descendants.get(required_uri, ())
                    )
                }
                gain = (
                    100.0 * sum(
                        float(requirements_by_uri[required_uri]["weight"])
                        for required_uri in newly_satisfied
                    ) / total_weight
                    if total_weight
                    else 0.0
                )
                return gain, newly_satisfied

            def cluster_for(uri: str) -> set[str]:
                cluster, frontier = set(), {uri}
                while frontier:
                    neighbours = set().union(
                        *(cluster_neighbours.get(member, set()) for member in frontier)
                    ) & remaining
                    frontier = neighbours - cluster - {uri}
                    cluster.update(frontier)
                return cluster | {uri}

            def projected_cluster_gain(uri: str) -> float:
                cluster_uris = cluster_for(uri)
                newly_satisfied = {
                    required_uri
                    for member in cluster_uris
                    for required_uri in requirements_by_uri
                    if required_uri not in satisfied
                    and (
                        required_uri == member
                        or member in descendants.get(required_uri, ())
                    )
                }
                return (
                    100.0 * sum(
                        float(requirements_by_uri[required_uri]["weight"])
                        for required_uri in newly_satisfied
                    ) / total_weight
                    if total_weight
                    else 0.0
                )

            ranked = sorted(
                (
                    (uri, *projected_gain(uri), projected_cluster_gain(uri))
                    for uri in ready
                ),
                key=lambda row: (
                    -row[1],
                    -row[3],
                    -float((hiring_evidence.get(row[0]) or {}).get("frequency") or 0.0),
                    labels.get(row[0], row[0]).casefold(),
                    row[0],
                ),
            )
            uri, gain, newly_satisfied, cluster_gain = ranked[0]
            requirement = requirements_by_uri[uri]
            prior = sorted(dependencies[uri] & (satisfied | set(learned_by)))
            resource = _learning_resource(requirement["skill"], resources)
            plan.append({
                "rank": len(plan) + 1,
                "skill": requirement["skill"],
                "uri": uri,
                "marginal_gain_pp": round(gain, 1),
                "cluster_gain_pp": round(cluster_gain, 1),
                "prerequisites": [labels[dependency] for dependency in prior if dependency in labels],
                "cluster_skills": [
                    labels[neighbour]
                    for neighbour in sorted(cluster_neighbours[uri])
                    if neighbour in labels
                ],
                "covered_by": labels.get(learned_by[uri]) if uri in learned_by else None,
                "hiring_evidence": hiring_evidence.get(uri),
                "resource": resource,
            })
            for required_uri in newly_satisfied:
                learned_by[required_uri] = uri
            satisfied.update(newly_satisfied)
            remaining.remove(uri)

        return plan

    @staticmethod
    def _market_delta(requirements: list[dict]) -> dict:
        total_weight = sum(item["weight"] for item in requirements)
        gaps = sorted(
            (item for item in requirements if item["credit"] == 0),
            key=lambda item: (
                -item.get(
                    "marginal_gain_pp",
                    100 * item["weight"] / total_weight if total_weight else 0,
                ),
                -(item["frequency"] if item["frequency"] is not None else -1),
            ),
        )
        high_roi_gaps = [
            {
                "skill": item["skill"],
                "frequency": item["frequency"],
                "readiness_gain_pp": round(
                    item.get(
                        "marginal_gain_pp",
                        100 * item["weight"] / total_weight if total_weight else 0,
                    ),
                    1,
                ),
                "evidence": item["evidence"],
                "hiring_evidence": (
                    (item.get("hiring_evidence") or {}).get("evidence")
                    if isinstance(item.get("hiring_evidence"), dict)
                    else None
                ),
            }
            for item in gaps[:8]
        ] if total_weight else []
        return {
            "high_roi_gaps": high_roi_gaps,
            "high_roi_note": (
                "Ranked by marginal CRI gain. Posting frequency and co-occurrence among matching job postings "
                "are supporting evidence, not a popularity cutoff."
            ),
            "emerging": None,
            "emerging_note": (
                "Skill trends compare the latest 90 days with the preceding 275 days of stored, "
                "deduplicated role postings."
            ),
        }


def _build_descendants(graph, engine) -> dict[str, set[str]]:
    if not graph:
        return {}
    children = graph.get("children", {})
    max_depth = max(1, int(getattr(engine, "INHERIT_MAX_DEPTH", 3)))
    max_descendants = max(1, int(getattr(engine, "INHERIT_MAX_DESC", 500)))
    descendants = {}
    for uri in children:
        seen: set[str] = set()
        frontier = {uri}
        for _ in range(max_depth):
            frontier = set().union(*(children.get(parent, set()) for parent in frontier)) - seen - {uri}
            seen.update(frontier)
            if not frontier or len(seen) > max_descendants:
                break
        if 0 < len(seen) <= max_descendants:
            descendants[uri] = seen
    return descendants


def _learning_resource(skill: str, resources=LEARNING_RESOURCES) -> dict[str, str]:
    normalized = skill.casefold()
    for keywords, title, provider, url in resources:
        if any(keyword in normalized for keyword in keywords):
            return {"title": title, "provider": provider, "url": url}
    return {
        "title": f"Find courses for {skill}",
        "provider": "Coursera course search",
        "url": f"https://www.coursera.org/search?query={quote_plus(skill)}",
    }


def _optional_number(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 3)
