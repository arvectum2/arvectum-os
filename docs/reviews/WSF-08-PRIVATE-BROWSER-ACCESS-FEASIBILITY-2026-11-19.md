# WSF-08 — private browser access feasibility

Candidate requirements only, not approved contract, implementation or activation. P10.09.20/API 15 at 37ccdcbff8da6ccad2d7e471c4a390f97039a27a. Goal: ordinary Owner work on MacBook without screen sharing, no public service, zero additional paid dependency proposed.

ADR-0001 sections 2.3–2.5 require HTTPS for non-loopback exposure, host-only Secure/HttpOnly/SameSite=Strict cookies, verified actor and Organization, CSRF and current authorization. Current product contracts and provider grants are local-only. Current listener 127.0.0.1:8769. Existing SSH and Screen Sharing transport verified; actual Owner GUI authentication not verified.

Current bootstrap trusts loopback and P704AccessResolver selects one enabled human and one active local credential. A generic proxy or SSH forwarding may present remote users as loopback; HTTPS alone is insufficient. Providers independently use access_path=local. Never expose/forward current bootstrap or disguise remote requests as local.

Nine synthetic ASGI observations PASS against existing BFF: direct remote bootstrap and spoofed forwarded header denied; bad host/origin denied; HTTPS scheme gives host-only Secure/HttpOnly/SameSite=Strict cookie; loopback bootstrap implicitly trusted; protected read succeeds; missing CSRF and revoked resolver denied. This characterizes the local exception, not remote readiness. No real TLS listener or live credentials used. Optional TestClient dependency absent from production venv; direct ephemeral ASGI fixture used, no install.

## Proposed minimum remote slice

1. Private HTTPS origin via existing private device network, subject to actual route, ACL, certificate trust and rotation review. No public Funnel, shared account, disabled certificate verification, new SaaS or production listener before approval. Keep existing local fallback.
2. Explicit human authentication before bootstrap. Evaluate Owner-bound passkey with user verification and separately registered device admission; confirm browser support, recovery, key custody and sovereignty/dependency review in an isolated spike. IP, SSH/Tailscale membership, device certificate alone or forwarded headers are not proof of human identity. Do not export local P7.04 secret.
3. Distinct server-derived access_path=remote, exact Organization/human/credential binding and explicit remote grant, revalidated on every protected operation. No fallback to local resolver. Existing resolver assumes one active human credential; review selection and provider gates before provisioning. Preserve current local rights, bounded sessions and revocation.
4. Initial separate contract proposal for read-only executive overview; specify routes/fields, expiry and handling. Remote exports, CRM/note edits, manual poll/review, Copilot and consequential actions denied until separately admitted. Company must determine utility; no inferred authorization.
5. Synthetic tests: trusted TLS, failed certificate/device/user verification, spoofed headers, replay, scope, missing remote grant, unadmitted route, CSRF/origin/host, no local bypass, revocation/expiry/logout/restart, logs/cache, release skew, local regression and rollback. Actual Safari on MacBook only after reviewed activation. No technical PASS as Owner adoption.

Owner review of exact scope/device/expiry/authentication strategy; OS contract/security review before implementation; exact CI and separate deployment/provisioning approval before live use. No production changes made.
