"""WSF-07 bounded repository metadata inbox candidate.

Only trusted server-side portfolio snapshots, not arbitrary URLs, raw documents,
mail, repository diffs, model output, or authoritative business records.
No live provider, scheduling, grants, or data admission in this module.
"""
from datetime import datetime, timezone
from uuid import uuid4
import json
from pathlib import Path
import re

from .wsf_manual_context import ManualContextStore, ManualContextError, _identity, _id, _keys, _json, _digest, MAX_BYTES, MAX_EVENTS
from .wsf_control_projection import stamp

SCHEMA = "arvectum.workspace.roadmap-inbox/1"
STATES = {"current-source-backed", "cached-source-backed", "stale-cache", "unavailable", "reconciliation-required"}
HEX40 = re.compile("[0-9a-f]{40}")
HEX64 = re.compile("[0-9a-f]{64}")


def registry_bindings(path=None):
    path = path or Path(__file__).with_name("company_project_registry.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema") != "arvectum.company.workspace-project-registry/1":
        raise ManualContextError("registry unavailable")
    result = {}
    for p in raw["projects"]:
        pid, repo, doc = p["id"], p["repository"], p["roadmap_path"]
        if pid in result or not re.fullmatch(r"COMPANY|OS|PORT-[0-9]{3}", pid):
            raise ManualContextError("invalid registry identity")
        if repo is not None and not re.fullmatch(r"arvectum2/[A-Za-z0-9_.-]+", repo):
            raise ManualContextError("invalid registry repository")
        if doc is not None and (not repo or not re.fullmatch(r"[A-Za-z0-9_./ -]+\.md", doc)
                or any(x in ("", ".", "..") for x in doc.split("/"))):
            raise ManualContextError("invalid registry path")
        result[pid] = {"repository":repo,"path":doc,"adapter":p["adapter"]}
    return result


def metadata_snapshot(projection, bindings, checked_at):
    """Project only verified identity/status; do not persist arbitrary source text."""
    now = stamp(checked_at)
    try:
        if (projection["schema"] != "arvectum.workspace.company-portfolio/1"
                or projection["projection"]["read_only"] is not True
                or projection["projection"]["canonical_authority"] is not False
                or projection["scope"]["organization_resolved_server_side"] is not True
                or projection["scope"]["actor_resolved_server_side"] is not True
                or projection["scope"]["cross_organization_aggregation"] is not False):
            raise ManualContextError("projection scope invalid")
        rows = {}
        for p in projection["projects"]:
            pid = p["id"]
            if pid not in bindings or pid in rows:
                raise ManualContextError("unknown or duplicate source")
            b = bindings[pid]
            if p["repository"] != b["repository"] or p["roadmap_path"] != b["path"]:
                raise ManualContextError("source locator mismatch")
            state = p["state"]
            if state not in STATES:
                raise ManualContextError("unknown source status")
            row = {"state":state,"source":None}
            if b["repository"] is None or b["path"] is None:
                if state != "reconciliation-required":
                    raise ManualContextError("unresolved binding")
            elif state == "current-source-backed":
                s = p["source"]
                if (s["repository"] != b["repository"] or s["path"] != b["path"]
                        or s["adapter"] != b["adapter"] or s["freshness"] != "fresh-fetch"
                        or not HEX40.fullmatch(s["commit_sha"]) or not HEX64.fullmatch(s["content_sha256"])):
                    raise ManualContextError("source identity invalid")
                fetched = stamp(s["fetched_at"])
                if not 0 <= (now-fetched).total_seconds() <= 300:
                    raise ManualContextError("fresh observation outside scan window")
                row["source"] = {k:s[k] for k in ("commit_sha","content_sha256","fetched_at")}
            rows[pid] = row
        if set(rows) != set(bindings):
            raise ManualContextError("incomplete registry scan")
        return rows
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ManualContextError("invalid scope or source observation") from exc


class _InboxFile(ManualContextStore):
    """Share only private file/lock/atomic replacement with the manual store."""
    def __init__(self, directory, access, bindings, *, require_initialized=False):
        directory=Path(directory)
        if directory.resolve()!=directory:
            raise ManualContextError("unsafe inbox directory")
        super().__init__(directory,access,require_initialized=require_initialized)
        self.require_initialized=True
        self.path=directory/"inbox.json"
        self.bindings=json.loads(_json(bindings))
        self.binding_digest=_digest(_json(self.bindings))

    def _encode(self,events):
        body={"schema":SCHEMA,"scope":self.scope,"registry_sha256":self.binding_digest,"events":events}
        raw=_json({**body,"sha256":_digest(_json(body))})
        if len(raw)>MAX_BYTES:raise ManualContextError("inbox capacity exceeded")
        return raw

    def _decode(self,raw):
        if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ManualContextError("inbox size invalid")
        try:
            d=json.loads(raw);_keys(d,{"schema","scope","registry_sha256","events","sha256"})
            if self._encode(d["events"])!=raw:raise ManualContextError("inbox integrity or scope mismatch")
            self.replay(d["events"])
            return d["events"]
        except (TypeError,KeyError,ValueError,UnicodeError,RecursionError,AttributeError) as exc:
            raise ManualContextError("invalid inbox snapshot") from exc

    def replay(self,events):
        if not isinstance(events,list) or len(events)>MAX_EVENTS:raise ManualContextError("inbox event limit")
        latest={};items={};commits={};seen={};last=None
        for e in events:
            _keys(e,{"key","operation","at","data"})
            key=_id(e["key"]);at=stamp(e["at"])
            if key in seen or last is not None and at<last:raise ManualContextError("duplicate or out-of-order event")
            last=at;seen[key]=e
            if e["operation"]=="scan":
                rows=e["data"]
                if not isinstance(rows,dict) or set(rows)!=set(self.bindings):raise ManualContextError("registry mismatch")
                for pid,row in rows.items():
                    _keys(row,{"state","source"})
                    state=row["state"];src=row["source"];old=latest.get(pid,{})
                    if state not in STATES:raise ManualContextError("invalid source status")
                    b=self.bindings[pid]
                    if (b["repository"] is None or b["path"] is None) and state!="reconciliation-required":
                        raise ManualContextError("unresolved source")
                    checkpoint=old.get("checkpoint")
                    if state=="current-source-backed":
                        _keys(src,{"commit_sha","content_sha256","fetched_at"})
                        if not HEX40.fullmatch(src["commit_sha"]) or not HEX64.fullmatch(src["content_sha256"]):
                            raise ManualContextError("invalid source revision")
                        fetched=stamp(src["fetched_at"])
                        if not 0<=(at-fetched).total_seconds()<=300 or checkpoint and fetched<stamp(checkpoint["fetched_at"]):
                            raise ManualContextError("out-of-order source version")
                        ck=(pid,src["commit_sha"])
                        if ck in commits and commits[ck]!=src["content_sha256"]:
                            raise ManualContextError("immutable commit conflict")
                        commits[ck]=src["content_sha256"]
                        if checkpoint and checkpoint["content_sha256"]!=src["content_sha256"]:
                            iid="INBOX-"+_digest(_json([pid,key]))[:32]
                            items[iid]={"id":iid,"source_id":pid,"repository":b["repository"],"path":b["path"],
                                "previous":checkpoint,"observed":src,"detected_at":e["at"],
                                "state":"pending","revision":1,"reviewed_at":None,"canonical_authority":False}
                        checkpoint=src
                    elif src is not None:raise ManualContextError("non-current source cannot advance checkpoint")
                    latest[pid]={"source_id":pid,"state":state,"checked_at":e["at"],"checkpoint":checkpoint}
            elif e["operation"]=="review":
                d=e["data"];_keys(d,{"item_id","expected_revision","state"})
                row=items.get(d["item_id"])
                if (row is None or type(d["expected_revision"]) is not int or row["revision"]!=d["expected_revision"]
                        or row["state"]!="pending" or d["state"] not in {"reviewed","dismissed"}):
                    raise ManualContextError("review revision or state conflict")
                items[row["id"]]={**row,"revision":row["revision"]+1,"state":d["state"],"reviewed_at":e["at"]}
            else:raise ManualContextError("unsupported inbox event")
        return latest,items,seen

    # This file type never accepts the unrelated manual-note operations.
    def submit(self,*a,**kw):raise ManualContextError("manual operations unavailable for inbox")
    def read(self,*a,**kw):raise ManualContextError("use inbox projection")
    def history(self,*a,**kw):raise ManualContextError("use inbox projection")


class RoadmapInbox:
    def __init__(self,directory,access,*,bindings,require_initialized=False):
        self.file=_InboxFile(directory,access,bindings,require_initialized=require_initialized)

    def initialize(self,access):
        self.file.restore_empty(access,self.file._encode([]))

    def _append(self,access,key,operation,data,at):
        f=self.file;f._authorize(access);_id(key);stamp(at)
        try:data=json.loads(_json(data))
        except (TypeError,ValueError) as exc:raise ManualContextError("invalid event") from exc
        with f._locked():
            events=f._load();_,_,seen=f.replay(events)
            if key in seen:
                old=seen[key]
                if (old["operation"],old["data"])!=(operation,data):raise ManualContextError("request replay conflict")
                return
            updated=events+[{"key":key,"operation":operation,"at":at,"data":data}]
            try:f._write(f._encode(updated))
            except (TypeError,KeyError,ValueError) as exc:raise ManualContextError("invalid inbox event") from exc

    def scan(self,access,key,projection,checked_at):
        self.file._authorize(access)
        self._append(access,key,"scan",metadata_snapshot(projection,self.file.bindings,checked_at),checked_at)

    def review(self,access,key,item_id,expected_revision,state,at):
        self._append(access,key,"review",{"item_id":item_id,"expected_revision":expected_revision,"state":state},at)

    def read(self,access,now=None):
        checked=stamp(now or datetime.now(timezone.utc).isoformat())
        f=self.file;f._authorize(access)
        with f._locked():
            sources,items,_=f.replay(f._load())
            for row in sources.values():
                row["freshness"]="current-observation" if row["state"]=="current-source-backed" and 0<=(checked-stamp(row["checked_at"])).total_seconds()<=4*3600 else "requires-refresh"
            return {"derived":True,"coverage":"partial" if sources else "unknown","canonical_authority":False,
                    "organizational_authority_provided":False,"sources":list(sources.values()),
                    "items":list(items.values()),"pending_count":sum(x["state"]=="pending" for x in items.values())}

    def export(self,access):return self.file.export(access)
    def restore_empty(self,access,raw):return self.file.restore_empty(access,raw)



def collect_once(inbox, *, provider, authorize, expected_scope, request_key=None):
    """A bounded poll entrypoint for a future explicitly admitted local job.

    The supplied provider must be the existing verified portfolio provider,
    with its registered fixed-locator reader (never browser-selected URLs).
    The authorization callable must revalidate machine/principal/source grants
    in the future productive binding. A revoked grant stops the commit.
    """
    from .company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider
    if not isinstance(provider, VerifiedRuntimeCompanyPortfolioProvider):
        raise ManualContextError("verified portfolio provider required")
    access=authorize()
    if _identity(access)!=expected_scope or inbox.file.scope!=expected_scope:
        raise ManualContextError("poll scope mismatch")
    provider_bindings={d.project_id:{"repository":d.repository,"path":d.roadmap_path,"adapter":d.adapter}
                       for d in provider._descriptors}
    if provider_bindings!=inbox.file.bindings:
        raise ManualContextError("poll registry mismatch")
    snapshot=provider.project(access,force_refresh=True)
    checked=datetime.now(timezone.utc).isoformat()
    current=authorize()
    if _identity(current)!=expected_scope or current.credential_id!=access.credential_id or current.grant_id!=access.grant_id:
        raise ManualContextError("poll authorization changed")
    inbox.scan(current,request_key or uuid4().hex,snapshot,checked)
    return inbox.read(current,checked)


def inbox_review_brief(inbox, access, now=None):
    """Deterministic source-linked suggestions, not AI-extracted facts or tasks."""
    view=inbox.read(access,now)
    suggestions=[]
    for row in view["items"]:
        if row["state"]!="pending":
            continue
        suggestions.append({"item_id":row["id"],"source_id":row["source_id"],
            "suggested_action":"review-source-change","requires_human_review":True,
            "source":{"repository":row["repository"],"path":row["path"],
                      "commit_sha":row["observed"]["commit_sha"],"content_sha256":row["observed"]["content_sha256"]},
            "previous_commit_sha":row["previous"]["commit_sha"],"detected_at":row["detected_at"],
            "business_impact":"unknown","canonical_authority":False})
    return {"coverage":view["coverage"],"suggestions":suggestions,
            "sources_needing_check":[r["source_id"] for r in view["sources"] if r["freshness"]!="current-observation"],
            "canonical_authority":False,"organizational_authority_provided":False}
