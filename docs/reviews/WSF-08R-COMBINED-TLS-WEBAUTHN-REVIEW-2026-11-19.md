# WSF-08R — combined TLS and WebAuthn experiment

Experimental evidence only. No approval of remote Product Contract, production integration, deployed remote profile, user verification on actual owner device or source admission. Stacked on PR #65.

## Evidence

A test-only HTTP-to-ASGI adapter binds an ephemeral IPv4 loopback socket with mutual TLS, validates the CA and exact client certificate pin from the actual TLS socket, and supplies the existing in-process fixture device proof to the synthetic BFF. No identity claims from headers, IP address or proxy. The fixture accepts only its synthetic origin or ephemeral HTTPS localhost origin; exact Host, Origin and RP ID. No live provider or production root.

Software authenticator registers an EC P-256 credential through real WebAuthn registration verification (none attestation, synthetic UV flag); real signature verification of subsequent assertions is required. Six combined cases PASS: full admission/read, wrong certificate/trust/hostname rejection, second valid but unregistered device and forged headers, invalid registration UV/origin/RP/challenge, bad authentication and local-only grant denial, exact host/origin/read-only route and CSRF logout/revocation. Previous TLS, ASGI/WebAuthn, P7.04 and config tests also PASS: 43/43. Additional manual-probe synthetic registration + authentication case PASS: 44/44 combined. No hardware attestation or actual human UV claimed. All test listeners ephemeral and closed.

## Actual MacBook passkey check

MacBook Air (macOS 27.2.1 / Safari 27.2 / Python 3.14.10) reached using existing ARC and SSH routes. Prepared owner-launched synthetic-only browser test, with existing hash-locked experimental dependencies installed in separate local directory. Verified script and lock SHA-256, Python import, registration options (platform attachment and required user verification), shell syntax and executable launcher. Server/JS syntax verified on Mac mini; complete synthetic registration and signature verification PASS, result created only after both ceremonies. Mac mini ephemeral localhost HTTP smoke PASS (HTML, JS, origin denial, options; no registration; listener closed). Two MacBook ARC ephemeral HTTP smoke attempts ended SIGKILL without output; actual Safari launch, secure-context support, and physical owner verification remain unverified. Do not claim actual device registration or change MacBook system security to force a test.

Launcher on MacBook desktop: Arvectum Passkey Test.command. It opens Safari against an isolated, temporary localhost origin with a random synthetic account, expires after five minutes if not completed. User must deliberately create the test passkey and separately confirm authentication. No company data, no real account, no production connection, no TLS trust installation, no daemon. The localhost HTTP secure-context experiment is not a remote transport acceptance test. Result records only status, time, test account and UV flags; no signature or reusable secret. Browser may save/sync the test passkey; clearly disclosed before enrollment; user removes it afterward. Actual authentication method (Touch ID or other platform verification) is not attested by this probe.

## Remaining gates

Genuine user-verified browser registration/authentication; device-bound private TLS ingress in the actual BFF topology, trust lifecycle, enrollment/revocation, remote credential selection and source-specific explicit remote grants; dependency/supply-chain review; exact reviewed remote contract, CI, separately approved deployment and actual Safari/HTTPS acceptance. Keep current local production and Screen Sharing fallback. No runtime, network config or grants changed.
