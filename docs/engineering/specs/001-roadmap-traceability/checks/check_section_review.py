"""Pinned source review; structural only, not product acceptance or task admission."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
DIR="docs/engineering/specs/001-roadmap-traceability"
PIN="83c0458fa108dd512ee0dbcd976238a3595a8f07"
PRIOR="0f02a32ce7190f38fcfc32dfec88f4767be96868"
MODE="governance_review"
SOURCES=json.loads("[{\"path\":\"docs/roadmap/ROADMAP.md\",\"sha256\":\"fa9ef4237955816e2ddc8d4d35e4de930a4d48724714c90c9d38594b42248175\"},{\"path\":\"docs/roadmap/WORKSPACE-FIRST-DELIVERY.md\",\"sha256\":\"5dd0c3af8a62ae4590301349f20bc4dd7cf44d32c437ad835e3e1d7fd537dcb9\"}]")
GATES=json.loads("[{\"id\":\"REVIEW-01\",\"source\":\"docs/roadmap/ROADMAP.md\",\"first_line\":127,\"last_line\":134,\"label\":\"P10 / R35 / R36\",\"rule\":\"Genuine action and owner-use evidence remain mandatory; no synthetic completion.\"},{\"id\":\"REVIEW-02\",\"source\":\"docs/roadmap/ROADMAP.md\",\"first_line\":291,\"last_line\":303,\"label\":\"M10 closure\",\"rule\":\"Retain every closure invariant; no new autonomy.\"},{\"id\":\"REVIEW-03\",\"source\":\"docs/roadmap/WORKSPACE-FIRST-DELIVERY.md\",\"first_line\":16,\"last_line\":24,\"label\":\"WSF-01–09\",\"rule\":\"Reconcile initial states with later dated entries, actual owner-use and contract gates.\"},{\"id\":\"REVIEW-04\",\"source\":\"docs/roadmap/WORKSPACE-FIRST-DELIVERY.md\",\"first_line\":175,\"last_line\":189,\"label\":\"Current local control\",\"rule\":\"Actual append and local release authority remain gated; no fresh AUTO work.\"}]")
def scan(raw):
    out=[];heading=0;fence=False
    for i,l in enumerate(raw.decode("utf-8").splitlines(),1):
        if not l.strip():continue
        if l.lstrip().startswith(("\x60\x60\x60","~~~")):
            fence=not fence;kind="format"
        elif fence:kind="code"
        elif re.match(r"^#{1,6}\s",l):heading=i;kind="heading"
        elif re.fullmatch(r"\s*\|?\s*[:\-]+(?:\s*\|\s*[:\-]+)+\s*\|?\s*",l) or re.fullmatch(r"\s*[-*_]{3,}\s*",l):kind="format"
        elif re.match(r"^\s*\|",l):kind="table"
        elif re.match(r"^\s*(?:[-*+]|\d+[.)])\s+",l):kind="list"
        else:kind="prose"
        out.append([i,heading,kind])
    return out
def validate(data,original,prior,current):
    errors=[]
    if data.get("schema")!="arvectum.source-section-review/1" or data.get("source_commit")!=PIN or data.get("review_baseline")!=PRIOR or data.get("mode")!=MODE or data.get("actual_acceptance_verified") is not False or data.get("execution_authorized") is not False:errors.append("scope/authority")
    if data.get("gates") is None: return errors+["missing gates"]
    src=data.get("sources",[]);paths=[s["path"] for s in src]
    if paths!=[s["path"] for s in SOURCES]:return errors+["source coverage"]
    for a,s in zip(src,SOURCES):
        p=s["path"];b=original[p]
        if hashlib.sha256(b).hexdigest()!=s["sha256"] or a.get("sha256")!=s["sha256"]:errors.append("source hash "+p)
        if not prior[p].startswith(b) or prior[p]!=current[p]:errors.append("unreviewed source change "+p)
        if a.get("rows")!=scan(b):errors.append("line/heading coverage "+p)
    rows=data["gates"]
    if len(rows)!=len(GATES):errors.append("gate coverage")
    for row,g in zip(rows,GATES):
        if any(row.get(k)!=v for k,v in g.items()):errors.append("gate identity/scope")
        if row.get("review_state") not in {"unverified","verified"}:errors.append("state")
        if row.get("review_state")=="verified":
            ev=row.get("evidence",[])
            if not ev or any(e.get("criterion")!=row["id"] or e.get("outcome")!="pass" or not re.fullmatch(r"[a-f0-9]{64}",e.get("artifact_sha256","")) or not e.get("receipt_ref") or not e.get("review_ref") for e in ev):errors.append("missing criterion-specific evidence "+row["id"])
    return errors
def inputs():
    def read(ref,p):return subprocess.check_output(["git","-C",str(ROOT),"show",ref+":"+p])
    original={s["path"]:read(PIN,s["path"]) for s in SOURCES}
    prior={p:read(PRIOR,p) for p in original}
    current={p:(ROOT/p).read_bytes() for p in original}
    return json.loads((ROOT/DIR/"section-review.json").read_text()),original,prior,current
if __name__=="__main__":
    errors=validate(*inputs())
    if errors:raise SystemExit("\n".join(errors))
    print("Structural source/section coverage PASS; no actual acceptance or authority.")
