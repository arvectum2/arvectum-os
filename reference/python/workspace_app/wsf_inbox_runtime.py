"""Owner-triggered productive inbox candidate, denied until exact publication.

No scheduler, credential export, new network connector or implicit AI authority.
The existing verified portfolio provider is reused without a new token.
"""
from datetime import datetime,timedelta,timezone
import hashlib,json,re
from pathlib import Path
from contextlib import nullcontext

import p7_04_persistent_access as p704
from .wsf_manual_context import ManualContextError,_identity,_json,_digest
from .wsf_manual_policy import _private_file
from .wsf_manual_runtime import RuntimeManualPilot
from .wsf_inbox_routes import FixtureInboxPilot,INBOX_PARTS
from .wsf_roadmap_inbox import RoadmapInbox,registry_bindings
from .wsf_manual_backup import PilotBackup
from .company_portfolio_verified import VerifiedRuntimeCompanyPortfolioProvider
from . import wsf_collector_runtime as collector

APPROVED_DRAFT="82c77613551a35ad1d2d1baa7c962673e427c8b0"
SUCCESSOR_DRAFT="0d9fda489f956f6ae8320b87978b443e4aef499b"
PREDECESSOR_REGISTRY="7f1dc7846decf648836f870324ae7baa4fd532dfcc4b96adc67f362fd273546a"
SUCCESSOR_REGISTRY="aa21ce050441c50f4b68c9dc7b16ebe43b1a5a29d4a98059a8616b35c2849016"
SUCCESSOR_PATH=Path(__file__).with_name("company_project_registry_061.json")
RESOURCE="roadmap-inbox"
OPERATIONS={x:"workspace.inbox."+x for x in ("read","poll","review","export")}
SCHEMA="arvectum.workspace.roadmap-inbox-policy/1"
RECEIPT_SCHEMA="arvectum.workspace.roadmap-inbox-activation/1"


class RuntimeInboxPilot:
    def __init__(self,root,*,approved_draft=APPROVED_DRAFT, successor_draft=SUCCESSOR_DRAFT, collector_publication=None):
        self.root=Path(root)
        self.approved_draft=approved_draft
        self.successor_draft=successor_draft
        self.manual=RuntimeManualPilot(self.root)
        self.collector_publication=collector_publication or collector.PUBLICATION_PIN

    def _gate(self,access,operation):
        if operation not in OPERATIONS or not self.approved_draft:
            raise ManualContextError("inbox not admitted")
        try:
            if self.root.resolve()!=self.root:raise ManualContextError("unsafe runtime")
            receipt=json.loads(_private_file(self.root/"config"/"roadmap-inbox-activation.json"))
            if (set(receipt)!={"schema","draft_blob","policy_sha256"} or receipt["schema"]!=RECEIPT_SCHEMA
                    or receipt["draft_blob"] not in (self.approved_draft,self.successor_draft) or not receipt["draft_blob"]):
                raise ManualContextError("approval mismatch")
            raw=_private_file(self.root/"config"/"roadmap-inbox-policy.json")
            if hashlib.sha256(raw).hexdigest()!=receipt["policy_sha256"]:raise ManualContextError("policy mismatch")
            p=json.loads(raw)
            draft=receipt["draft_blob"]
            registry=SUCCESSOR_PATH if draft==self.successor_draft else None
            bindings=registry_bindings(registry)
            if draft==self.successor_draft and _digest(_json(bindings))!=SUCCESSOR_REGISTRY:
                raise ManualContextError("successor registry pin mismatch")
            if (set(p)!={"schema","draft_blob","registry_sha256","scope","credential_id","starts_at","expires_at","grants","purpose"}
                    or p["schema"]!=SCHEMA or p["draft_blob"]!=draft
                    or p["registry_sha256"]!=_digest(_json(bindings))
                    or p["scope"]!=_identity(access) or p["credential_id"]!=access.credential_id
                    or p["purpose"]!="owner-triggered-roadmap-metadata"
                    or set(p["grants"])!=set(OPERATIONS.values())
                    or any(not re.fullmatch("[0-9a-f]{32}",v) for v in p["grants"].values())
                    or len(set(p["grants"].values()))!=len(OPERATIONS)):
                raise ManualContextError("policy binding mismatch")
            start,end=(datetime.fromisoformat(p[k]) for k in ("starts_at","expires_at"))
            if (start.utcoffset()!=timedelta(0) or end.utcoffset()!=timedelta(0)
                    or not start<=datetime.now(timezone.utc)<end or end-start>timedelta(days=30)):
                raise ManualContextError("policy expired")
            review=self.manual.review_signal(access)
            if end>datetime.fromisoformat(review["due_at"]):raise ManualContextError("predecessor expiry exceeded")
            if not re.fullmatch("[0-9a-f]{32}",access.credential_id):raise ManualContextError("credential invalid")
            exact=OPERATIONS[operation]
            d=p704.authorize_from_credential_file(self.root,organization=access.organization,principal=access.actor,
                credential_id=access.credential_id,credential_file=self.root/"secrets"/"p7-04"/(access.credential_id+".secret"),
                operation=exact,resource=RESOURCE,access_path="local")
            if not d.allowed or d.principal_kind!="human" or d.grant_id!=p["grants"][exact]:
                raise ManualContextError("exact grant unavailable")
            if collector.present(self.root,collector.JOURNAL):
                raise ManualContextError("inbox cutover incomplete")
            if collector.present(self.root,collector.RECEIPT) or collector.present(self.root,collector.CONFIG):
                if draft!=self.successor_draft:raise ManualContextError("collector predecessor mismatch")
                inbox=collector.human_inbox(self.root,access,publication=self.collector_publication)
            else:
                inbox=RoadmapInbox(self.root/"workspace-company-roadmap-inbox",access,bindings=bindings,require_initialized=True)
            inbox.read(access)
            return inbox,start,end,registry
        except (OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError,p704.P704Error) as exc:
            raise ManualContextError("inbox unavailable") from exc

    def authorize(self,access,operation):
        return self._gate(access,operation)[0]

    def backup(self,access):
        s=self.authorize(access,"export")
        return PilotBackup(s.file,parts=INBOX_PARTS).copy_latest(access)

    def read(self,access):
        s=self.authorize(access,"read")
        d=s.read(access)
        try:
            b=PilotBackup(self.authorize(access,"export").file,parts=INBOX_PARTS)
            d["backup_status"]="verified" if b.verified_snapshot(access)==s.export(access) else "stale"
        except (OSError,ManualContextError):d["backup_status"]="unavailable"
        if isinstance(s,collector.CollectorInbox):
            from .wsf_collector_runner import read_status
            try:
                status=read_status(self.root)
                config,policy=collector.load_config(self.root,publication=self.collector_publication)
                if status and status["release_sha"]!=policy.release_sha:
                    raise ManualContextError("collector status release mismatch")
                d["collector"].update({"run_state":status["state"] if status else "not-run",
                    "last_verified_at":status["last_verified_at"] if status else None,
                    "next_window_at":datetime.fromtimestamp((status["window"]+1)*10800,timezone.utc).isoformat() if status else None,
                    "expires_at":policy.expires_at.isoformat(),
                    "release_sha":policy.release_sha})
            except (OSError,ManualContextError,ValueError,TypeError):
                d["collector"].update({"run_state":"unknown","last_verified_at":None,"next_window_at":None,"expires_at":None,"release_sha":None})
        return d

    def mutate(self,authorize,operation,data):
        access=authorize()
        inbox,start,end,registry=self._gate(access,operation)
        self.authorize(access,"export")
        worker=FixtureInboxPilot(inbox,VerifiedRuntimeCompanyPortfolioProvider(registry_path=registry),
            PilotBackup(inbox.file,parts=INBOX_PARTS),access.credential_id,
            access.grant_id,start,end,frozenset({operation}))
        def guard():
            a=authorize()
            if isinstance(inbox,collector.CollectorInbox) and (self.root/"run"/"p7-06-deploy.lock").exists():
                raise ManualContextError("deployment active")
            self.authorize(a,operation)
            self.authorize(a,"export")
            return a
        # Full manual poll/review, including backup and network fetch, shares the
        # service-cycle gate. No weaker lock for a migrated ledger.
        lock=inbox.file.cycle_lock() if isinstance(inbox,collector.CollectorInbox) else nullcontext()
        with lock:
            if isinstance(inbox,collector.CollectorInbox) and (self.root/"run"/"p7-06-deploy.lock").exists():
                raise ManualContextError("deployment active")
            return worker.mutate(guard,operation,data)
