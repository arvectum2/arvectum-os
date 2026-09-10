from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .access import AccessContext


class CompanyPortfolioError(RuntimeError):
    """The Company portfolio projection cannot be produced safely."""


_ALLOWED_TARGETS = frozenset(
    {
        "web",
        "mac-mini",
        "macbook",
        "windows-laptop",
        "windows-test-laptop",
        "linux-test-laptop",
        "unspecified",
    }
)
_REPOSITORY_RE = re.compile(r"^arvectum2/[A-Za-z0-9_.-]+$")
_PATH_RE = re.compile(r"^[A-Za-z0-9_./ -]+\.md$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_STAGE_HEADING_RE = re.compile(r"^##\s+(R\d+(?:\.\d+)?)\s+[—-]\s+(.+?)\s*$", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _plain(line: str) -> str:
    text = line.strip().strip("`|#*- >")
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("|", " — ")
    return " ".join(text.split())


def _bounded(text: str, limit: int = 640) -> str:
    value = " ".join(str(text).split())
    return value[:limit]


def _first_value(markdown: str, labels: tuple[str, ...]) -> str | None:
    for raw in markdown.splitlines():
        line = raw.strip()
        for label in labels:
            if line.lower().startswith(label.lower()):
                value = _plain(line[len(label) :].lstrip(" :—-"))
                if value:
                    return _bounded(value)
    return None


def _matching_lines(markdown: str, tokens: tuple[str, ...], *, limit: int = 6) -> list[str]:
    if limit <= 0:
        return []
    result: list[str] = []
    seen: set[str] = set()
    upper_tokens = tuple(token.upper() for token in tokens)
    for raw in markdown.splitlines():
        upper = raw.upper()
        if not any(token in upper for token in upper_tokens):
            continue
        value = _plain(raw)
        if not value or len(value) < 4 or value in seen:
            continue
        seen.add(value)
        result.append(_bounded(value))
        if len(result) >= limit:
            break
    return result


def _section_body(markdown: str, section_title: str) -> list[str]:
    active = False
    active_level = 0
    body: list[str] = []
    needle = section_title.casefold()
    for raw in markdown.splitlines():
        match = _HEADING_RE.match(raw.strip())
        if not active:
            if match and needle in match.group(2).casefold():
                active = True
                active_level = len(match.group(1))
            continue
        if match and len(match.group(1)) <= active_level:
            break
        body.append(raw)
    return body


def _section_headings(markdown: str, section_title: str, *, limit: int = 6) -> list[str]:
    result: list[str] = []
    for raw in _section_body(markdown, section_title):
        match = _HEADING_RE.match(raw.strip())
        if not match:
            continue
        value = _bounded(_plain(match.group(2)))
        if value:
            result.append(value)
        if len(result) >= limit:
            break
    return result


def _table_rows_in_section(markdown: str, section_title: str, *, limit: int = 8) -> list[str]:
    result: list[str] = []
    for raw in _section_body(markdown, section_title):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("*`") for cell in line.strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{3,}:?", cell or "---") for cell in cells):
            continue
        if cells[0].casefold() in {"id", "lane", "phase", "block"}:
            continue
        value = _bounded(" — ".join(cell for cell in cells if cell))
        if value and value not in result:
            result.append(value)
        if len(result) >= limit:
            break
    return result


def _stage_progress(markdown: str) -> tuple[list[str], list[str]]:
    lines = markdown.splitlines()
    stages: list[tuple[str, int, int]] = []
    for index, raw in enumerate(lines):
        match = _STAGE_HEADING_RE.match(raw.strip())
        if match:
            stages.append((f"{match.group(1).upper()} — {_plain(match.group(2))}", index, len(lines)))
    if not stages:
        return [], []
    bounded: list[tuple[str, int, int]] = []
    for pos, (label, start, _) in enumerate(stages):
        end = stages[pos + 1][1] if pos + 1 < len(stages) else len(lines)
        bounded.append((label, start, end))
    done: list[str] = []
    remaining: list[str] = []
    for label, start, end in bounded:
        section = "\n".join(lines[start:end]).upper()
        if re.search(r"СТАТУС\s*:\s*(?:\*\*)?DONE", section) or re.search(r"STATUS\s*:\s*(?:\*\*)?DONE", section):
            done.append(label)
        else:
            remaining.append(label)
    return done[:6], remaining[:6]


def _source_execution_targets(markdown: str) -> list[str]:
    upper = markdown.upper()
    targets: list[str] = []

    def add(value: str) -> None:
        if value not in targets:
            targets.append(value)

    if re.search(r"\[WEB(?:/DECISION)?\]", upper) or "GITHUB IMPLEMENTATION" in upper:
        add("web")
    if "MAC MINI" in upper:
        add("mac-mini")
    if "MACBOOK" in upper:
        add("macbook")
    if "ARVECTUM-DEMO" in upper and "[WIN" in upper:
        add("windows-test-laptop")
    if "ARVECTUM-DEMO" in upper and "[LINUX" in upper:
        add("linux-test-laptop")
    return targets


def _empty_roadmap() -> dict[str, Any]:
    return {
        "status": None,
        "version": None,
        "source_updated": None,
        "done": [],
        "current": [],
        "branches": [],
        "unlocked": [],
        "blocked": [],
    }


@dataclass(frozen=True, slots=True)
class ProjectDescriptor:
    project_id: str
    label: str
    kind: str
    disposition: str
    repository: str | None
    roadmap_path: str | None
    adapter: str
    execution_targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceDocument:
    repository: str
    path: str
    commit_sha: str
    markdown: str
    fetched_at: str


class GitHubRoadmapReader:
    """Server-side read-only GitHub source reader over packaged allowlisted descriptors."""

    def __init__(self, token: str | None = None, *, timeout_seconds: float = 8.0) -> None:
        self.token = token if token is not None else os.getenv("ARVECTUM_WORKSPACE_GITHUB_TOKEN")
        self.timeout_seconds = timeout_seconds

    def _json(self, url: str) -> dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Arvectum-OS-Workspace-F11",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            with urlopen(Request(url, headers=headers), timeout=self.timeout_seconds) as response:  # noqa: S310 - fixed allowlisted host
                raw = response.read(2_000_000)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise CompanyPortfolioError("canonical roadmap source unavailable") from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CompanyPortfolioError("canonical roadmap response invalid") from exc
        if not isinstance(payload, dict):
            raise CompanyPortfolioError("canonical roadmap response invalid")
        return payload

    def read(self, descriptor: ProjectDescriptor) -> SourceDocument:
        if descriptor.repository is None or not _REPOSITORY_RE.fullmatch(descriptor.repository):
            raise CompanyPortfolioError("canonical repository locator requires reconciliation")
        if descriptor.roadmap_path is None or not _PATH_RE.fullmatch(descriptor.roadmap_path):
            raise CompanyPortfolioError("canonical roadmap source requires reconciliation")
        repository = descriptor.repository
        commit = self._json(f"https://api.github.com/repos/{repository}/commits/main")
        sha = commit.get("sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise CompanyPortfolioError("canonical source SHA unavailable")
        source_path = quote(descriptor.roadmap_path, safe="/")
        source = self._json(f"https://api.github.com/repos/{repository}/contents/{source_path}?ref={sha}")
        encoded = source.get("content")
        encoding = source.get("encoding")
        if encoding != "base64" or not isinstance(encoded, str):
            raise CompanyPortfolioError("canonical roadmap bytes unavailable")
        try:
            markdown = base64.b64decode(encoded, validate=False).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise CompanyPortfolioError("canonical roadmap content invalid") from exc
        if len(markdown) > 1_500_000:
            raise CompanyPortfolioError("canonical roadmap exceeds bounded reader limit")
        return SourceDocument(repository, descriptor.roadmap_path, sha, markdown, _utc_now())


def _normalize(descriptor: ProjectDescriptor, source: SourceDocument) -> dict[str, Any]:
    markdown = source.markdown
    status = _first_value(markdown, ("Статус", "Status", "Stage"))
    version = _first_value(markdown, ("Версия", "Version", "Current product line"))
    updated = _first_value(markdown, ("Обновлено", "Updated", "Дата фиксации"))
    current: list[str] = []
    branches: list[str] = []
    unlocked: list[str] = []
    blocked: list[str] = []
    done: list[str] = []

    if descriptor.adapter == "company-roadmap-v1":
        current_action = _first_value(markdown, ("Текущее каноническое действие",))
        if current_action:
            current.append(current_action)
        branches = _section_headings(markdown, "Available implementation paths now")
        unlocked = branches[:]
        blocked = _matching_lines(markdown, ("EXTERNAL EVIDENCE WAIT", " NOT ADMITTED", " LOCKED", " BLOCKED"), limit=5)
        done = _matching_lines(markdown, ("COMPLETE / PASS",), limit=5)
    elif descriptor.adapter == "os-roadmap-v1":
        canonical_action = "\n".join(_section_body(markdown, "Current canonical actions"))
        current = _matching_lines(canonical_action, ("P9.11 —",), limit=1)
        if not current:
            current = _matching_lines(markdown, ("P9.11", "NEXT CANONICAL ACTION"), limit=2)
        branches = _table_rows_in_section(markdown, "Parallel development lanes", limit=5)
        unlocked = [row for row in branches if any(token in row.upper() for token in ("CRITICAL PATH", "AVAILABLE", "CONTINUOUS"))][:5]
        blocked = _matching_lines(markdown, ("R32", "LOCKED", "BLOCKED ON REAL ENDPOINT"), limit=5)
        done = _matching_lines("\n".join(_section_body(markdown, "Active Phase 9")), ("COMPLETE / PASS", "ACHIEVED / PASS"), limit=5)
    elif descriptor.adapter == "proxy-roadmap-v1":
        available = "\n".join(_section_body(markdown, "What can be done now"))
        current = _matching_lines(available, ("CURRENT —", "CURRENT — APL", "CURRENT"), limit=4)
        branches = _section_headings(markdown, "What can be done now", limit=6)
        unlocked = _matching_lines(available, ("READY", "CURRENT"), limit=6)
        blocked = _matching_lines(markdown, ("STOP-GATE", "HUMAN/LEGAL PENDING", "ADMIN PENDING"), limit=5)
        done = _matching_lines(available, ("DONE",), limit=5)
    elif descriptor.adapter == "creative-roadmap-v1":
        if status is None and "Current state" in markdown:
            status = "Current"
        current_state = "\n".join(_section_body(markdown, "Current state"))
        next_task = _first_value(current_state, ("next task",))
        if next_task:
            current.append(next_task)
        if not current:
            current = _matching_lines(current_state or markdown, ("NEXT TASK", "CURRENT PRIORITY"), limit=2)
        done = _matching_lines(current_state or markdown, ("DONE", "COMPLETE"), limit=5)
        blocked = _matching_lines(current_state or markdown, ("BLOCKED", "WAITING-FOR-DATA"), limit=4)
        branches = _matching_lines(current_state or markdown, ("LANE",), limit=3)
        unlocked = current[:]
    elif descriptor.adapter == "tender-status-v1":
        next_milestone = "\n".join(_section_body(markdown, "Next milestone"))
        current = _matching_lines(next_milestone, ("NEXT STAGE",), limit=2)
        if not current:
            current = [_bounded(_plain(line)) for line in _section_body(markdown, "Next milestone") if _plain(line)][:2]
        done = _matching_lines(markdown, ("PASS", "R0_CLOSED_FUNCTIONALLY"), limit=5)
        blocked = _matching_lines(markdown, ("NOT PROVEN", "OUT OF R0", "REQUIRED"), limit=5)
        branches = []
        unlocked = current[:]
    else:
        stage_done, stage_remaining = _stage_progress(markdown)
        if stage_done or stage_remaining:
            done = stage_done
            if stage_remaining:
                current = [stage_remaining[0]]
                unlocked = [stage_remaining[0]]
                branches = stage_remaining[1:6]
        else:
            current = _matching_lines(markdown, ("CURRENT", "ТЕКУЩ", "NEXT", "СЛЕДУЮЩ"), limit=5)
            unlocked = _matching_lines(markdown, ("READY", "ГОТОВО К", "ДОСТУП"), limit=5)
            done = _matching_lines(markdown, ("DONE", "COMPLETE", "PASS", "ГОТОВО"), limit=5)
        blocked = _matching_lines(markdown, ("BLOCKED", "PENDING", "LOCKED", "ЗАБЛОК", "HOLD"), limit=5)

    return {
        "status": status,
        "version": version,
        "source_updated": updated,
        "done": done,
        "current": current,
        "branches": branches,
        "unlocked": unlocked,
        "blocked": blocked,
    }


class RuntimeCompanyPortfolioProvider:
    def __init__(self, registry_path: Path | None = None, *, reader: GitHubRoadmapReader | None = None) -> None:
        self.registry_path = registry_path or Path(__file__).with_name("company_project_registry.json")
        self.reader = reader or GitHubRoadmapReader()
        self._descriptors, self._authority = self._load_registry()

    def _load_registry(self) -> tuple[tuple[ProjectDescriptor, ...], dict[str, str]]:
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CompanyPortfolioError("Company project registry unavailable") from exc
        if payload.get("schema") != "arvectum.company.workspace-project-registry/1":
            raise CompanyPortfolioError("Company project registry schema mismatch")
        authority = payload.get("authority")
        projects = payload.get("projects")
        if not isinstance(authority, dict) or not isinstance(projects, list):
            raise CompanyPortfolioError("Company project registry invalid")
        descriptors: list[ProjectDescriptor] = []
        ids: set[str] = set()
        for item in projects:
            if not isinstance(item, dict):
                raise CompanyPortfolioError("Company project registry invalid")
            targets = tuple(item.get("execution_targets", ()))
            if any(target not in _ALLOWED_TARGETS for target in targets):
                raise CompanyPortfolioError("Company execution target outside contract")
            raw_repository = item.get("repository")
            repository = raw_repository if isinstance(raw_repository, str) and raw_repository else None
            roadmap_path = item.get("roadmap_path")
            if repository is not None and not _REPOSITORY_RE.fullmatch(repository):
                raise CompanyPortfolioError("Company repository locator invalid")
            if roadmap_path is not None and (not isinstance(roadmap_path, str) or not _PATH_RE.fullmatch(roadmap_path)):
                raise CompanyPortfolioError("Company roadmap locator invalid")
            if roadmap_path is not None and repository is None:
                raise CompanyPortfolioError("Company roadmap cannot exist without a reconciled repository")
            descriptor = ProjectDescriptor(
                project_id=str(item.get("id", "")),
                label=str(item.get("label", "")),
                kind=str(item.get("kind", "")),
                disposition=str(item.get("disposition", "")),
                repository=repository,
                roadmap_path=roadmap_path,
                adapter=str(item.get("adapter", "")),
                execution_targets=targets,
            )
            if not descriptor.project_id or descriptor.project_id in ids or not descriptor.label:
                raise CompanyPortfolioError("Company project identity invalid")
            ids.add(descriptor.project_id)
            descriptors.append(descriptor)
        return tuple(descriptors), {str(k): str(v) for k, v in authority.items()}

    def project(self, access: AccessContext) -> dict[str, Any]:
        if not isinstance(access, AccessContext):
            raise CompanyPortfolioError("server-authorized AccessContext is required")
        cards: list[dict[str, Any]] = []
        for descriptor in self._descriptors:
            base_targets = list(descriptor.execution_targets) or ["unspecified"]
            base = {
                "id": descriptor.project_id,
                "label": descriptor.label,
                "kind": descriptor.kind,
                "disposition": descriptor.disposition,
                "repository": descriptor.repository,
                "roadmap_path": descriptor.roadmap_path,
                "execution_targets": base_targets,
                "authority_mode": "External Reference",
                "projection_authority": "non-authoritative",
            }
            if descriptor.repository is None or descriptor.roadmap_path is None:
                reason = (
                    "Канонический repository locator требует reconciliation."
                    if descriptor.repository is None
                    else "Канонический roadmap/status source для этого проекта пока не стандартизирован."
                )
                cards.append({**base, "state": "reconciliation-required", "message": reason, "source": None, "roadmap": _empty_roadmap()})
                continue
            try:
                source = self.reader.read(descriptor)
                roadmap = _normalize(descriptor, source)
            except CompanyPortfolioError:
                cards.append(
                    {
                        **base,
                        "state": "unavailable",
                        "message": "Канонический источник сейчас недоступен; статус не подменяется кэшем или памятью модели.",
                        "source": None,
                        "roadmap": _empty_roadmap(),
                    }
                )
                continue
            source_targets = list(descriptor.execution_targets) or _source_execution_targets(source.markdown) or ["unspecified"]
            cards.append(
                {
                    **base,
                    "execution_targets": source_targets,
                    "state": "current-source-backed",
                    "message": "Данные прочитаны напрямую из зарегистрированного канонического roadmap/status source.",
                    "source": {
                        "repository": source.repository,
                        "path": source.path,
                        "commit_sha": source.commit_sha,
                        "fetched_at": source.fetched_at,
                        "freshness": "fresh-fetch",
                        "adapter": descriptor.adapter,
                    },
                    "roadmap": roadmap,
                }
            )
        return {
            "schema": "arvectum.workspace.company-portfolio/1",
            "generated_at": _utc_now(),
            "product_contract": {"id": "P9.11-F11", "version": "0.1.0", "lifecycle": "Provisional"},
            "projection": {
                "derived": True,
                "canonical_authority": False,
                "read_only": True,
                "roadmap_write_available": False,
                "remote_execution_available": False,
                "chat_or_model_memory_used_as_authority": False,
                "visibility_implies_permission": False,
            },
            "scope": {
                "organization_resolved_server_side": True,
                "actor_resolved_server_side": True,
                "cross_organization_aggregation": False,
            },
            "registry_authority": self._authority,
            "projects": cards,
        }


__all__ = [
    "CompanyPortfolioError",
    "GitHubRoadmapReader",
    "ProjectDescriptor",
    "RuntimeCompanyPortfolioProvider",
    "SourceDocument",
]
