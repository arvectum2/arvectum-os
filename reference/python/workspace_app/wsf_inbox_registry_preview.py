"""Offline-only registry reconciliation preview for the fixed WSF-07A ledger.

No policy pin modification, production writes, network fetch or new authority.
The caller creates separate private scratch stores and supplies an independently
reviewed exact target registry. A live migration needs its own approved cutover.
"""
from .wsf_manual_context import ManualContextError,_digest,_json


def preview_resolved_bindings(access,source,target):
    """Return validated candidate bytes, preserving all existing event history.

    Only an unresolved document locator in an already bound repository may
    become resolved. Identity sets and existing resolved descriptors cannot
    change. Old rows for the changed source must all be explicit unresolved
    observations; no historical checkpoint may be reinterpreted.
    """
    old,new=source.file,target.file
    if old.directory==new.directory or old.scope!=new.scope:
        raise ManualContextError("separate same-scope preview required")
    old._authorize(access);new._authorize(access)
    if new.path.exists() or new.path.is_symlink():
        raise ManualContextError("target must be empty")
    if set(old.bindings)!=set(new.bindings):
        raise ManualContextError("registry identity change not admitted")
    changed=[]
    for pid,b in old.bindings.items():
        n=new.bindings[pid]
        if b==n:continue
        if (not b["repository"] or b["path"] is not None or b["adapter"]!="reconciliation-required"
            or n["repository"]!=b["repository"] or not n["path"]
            or n["adapter"]!="generic-roadmap-v1"):
            raise ManualContextError("only unresolved existing locator may be resolved")
        changed.append(pid)
    if not changed:raise ManualContextError("no locator reconciliation")
    raw=source.export(access)
    events=old._decode(raw)
    for event in events:
        if event["operation"]=="scan":
            for pid in changed:
                if event["data"][pid]!={"state":"reconciliation-required","source":None}:
                    raise ManualContextError("historical checkpoint cannot be rebound")
    candidate=new._encode(events)
    verified=new._decode(candidate)
    before=old.replay(events)
    after=new.replay(verified)
    if before!=after or events!=verified:
        raise ManualContextError("historical projection changed")
    return candidate,{"changed":sorted(changed),"event_count":len(events),
        "source_sha256":_digest(raw),"candidate_sha256":_digest(candidate),
        "old_registry_sha256":old.binding_digest,"new_registry_sha256":new.binding_digest,
        "history_preserved":True,"canonical_authority":False}
