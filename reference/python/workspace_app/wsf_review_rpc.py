"""Bounded protocol over a separately authenticated, integrity-protected transport.

Server dispatch must be composed under an independently controlled account with
fixed trust and authenticated operator. No network endpoint or bootstrap here.
"""
import base64,json
from .wsf_review_ticket import Ticket,need,hex64
from .wsf_manual_context import _json,ManualContextError

MAX=32768
def decode(raw):
    need(type(raw) is bytes and 0<len(raw)<=MAX,"RPC message bound")
    try:
        obj=json.loads(raw);need(type(obj) is dict and _json(obj)==raw,"RPC canonical bytes")
        return obj
    except (ValueError,TypeError,RecursionError) as exc:raise ManualContextError("RPC format denied") from exc
def head(v):
    need(type(v) in (tuple,list) and len(v)==3 and type(v[0]) is int and 0<=v[0]<=1000
        and hex64(v[1]) and hex64(v[2]),"RPC head format")
    return tuple(v)
def dispatch(raw,*,store,clock):
    """No path, client-selected trust, clock, admin or signing parameters."""
    q=decode(raw);op=q.get("operation");trust=store.trust
    need(q.get("register")==trust.register,"RPC resource")
    if op in ("head","read_head"):
        need(set(q)=={"operation","register"},"RPC read keys")
        result=(store.head if op=="head" else store.read_head)(trust.register)
        return _json({"head":result})
    need(op in ("check","reserve","commit"),"RPC operation denied")
    keys={"operation","register","ticket","signature"}|({"old","new"} if op=="commit" else set())
    need(set(q)==keys,"RPC request keys")
    try:
        t=Ticket.decode(base64.b64decode(q["ticket"],validate=True))
        sig=base64.b64decode(q["signature"],validate=True)
    except (ValueError,TypeError) as exc:raise ManualContextError("RPC ticket encoding") from exc
    now=clock()
    if op=="check":store.check_live(trust,t,sig,now)
    elif op=="reserve":store.reserve(trust,t,sig,now)
    else:store.compare_and_set(trust.register,head(q["old"]),head(q["new"]),trust,t,sig,now)
    return _json({"ok":True})

class RemoteAuthority:
    def __init__(self,trust,exchange):
        self.trust=trust;self.exchange=exchange
    def request(self,op,register,**kwargs):
        need(register==self.trust.register,"RPC register")
        # exchange is a trusted authenticated channel, never candidate controlled.
        try:return decode(self.exchange(_json({"operation":op,"register":register,**kwargs})))
        except (OSError,TimeoutError) as exc:raise ManualContextError("authority unavailable") from exc
    def head(self,register):
        v=self.request("head",register);need(set(v)=={"head"},"RPC response");return head(v["head"])
    def read_head(self,register):
        v=self.request("read_head",register);need(set(v)=={"head"},"RPC response");return head(v["head"])
    def ticket(self,op,trust,t,sig,**kwargs):
        need(trust==self.trust,"RPC trust mismatch")
        v=self.request(op,trust.register,ticket=base64.b64encode(t.raw()).decode(),signature=base64.b64encode(sig).decode(),**kwargs)
        need(v=={"ok":True},"RPC denied")
    def check_live(self,trust,t,sig,now):self.ticket("check",trust,t,sig)
    def reserve(self,trust,t,sig,now):self.ticket("reserve",trust,t,sig)
    def compare_and_set(self,register,old,new,trust,t,sig,now):
        need(register==trust.register,"RPC resource");self.ticket("commit",trust,t,sig,old=old,new=new)
