# WSF-04C — Selected Mac technical pilot activation evidence

Date: 2026-11-17.
Status: technical activation PASS; owner-use acceptance pending.
Company decision: [approved pilot parameters](https://github.com/arvectum2/arvectum-company/blob/0930bb12b905926a10162e04b293e160808485a2/docs/governance/decisions/DECISION-2026-11-17-WSF-04C-PILOT-PARAMETERS.md).
Contract: [Provisional 0.4.0](../contracts/WSF-04C-ARVECTUM-COMPANY-WORKSPACE-PRODUCT-CONTRACT-PROVISIONAL-v0.4.0.md), exact Draft blob 124c2e3b7bee7e89109d5f27d1d0f4f79fb3f7b2.
Owner explicitly directed completion and permitted activation: “делай. разрешаю”.

## Exact implementation and deployment

- Company PR #15 merged 0930bb12b905926a10162e04b293e160808485a2.
- OS PR #27 merged daeeb3dfa43bac71fb021f42c7a712796cfd0a77; exact reviewed draft preserved.
- OS PR #28 exact head 83160ee2c390d7f40f25ffe657731e5ffb3c3b28: four CI gates SUCCESS (BFF, full reference, SPA/storage, mirror), merged 44c56045f02d40fdd6f72caf6c428f8b1c288b71.
- Focused Mac mini checks: 28 store/backup/policy/runtime tests, 7 SPA tests, typecheck, build, browser-storage guard and exact release asset verification PASS. Separate synthetic real P7.04 activation exercise with five grants, project/capture and revoked-capture denial PASS. Prior independent physical disk synthetic restore PASS; not real Owner usage.
- Governed P7.06 deploy source 77a5ce0343bf1e677726788c649045e3596fa20b, target 44c56045f02d40fdd6f72caf6c428f8b1c288b71, transaction 2dbeae5962cec56574bb6c0af68fd074d735511199e8e5f8be5051b76be64f9c. Pre-update backup independently verified SHA-256 acac0d02f9c8be7ada5e6a2f1c712eba1332c91164c8801f319bbc9bffc2c392. P7.02 PASS generation 88, P7.05 HEALTHY, UI3 PASS and Workspace CURRENT_EXACT. Release p10.09.5, internal API contract 15, loopback listener only. Operator logs retained.

## Observed activation

- Started 2026-11-17T09:35:36.060836Z; expires 2026-12-17T09:35:36.060836Z (30 days; 12:35:36 Moscow local). Activation only after merged publication and governed deployment. Policy SHA-256 45edc52fb73a20fa73c79a6eda9c2a77ee91f62f2a22a43b1a0aab67602ff22a. Five exact local operation grants; no credentials or business data in Git.
- Physical internal primary under persistent-internal/workspace-company-manual-context/context.json, encrypted external APFS latest copy under /Volumes/ArvectumSSD/Arvectum/backups/arvectum-os/manual-context/latest.private.json. Different st_dev values, private modes. Empty snapshot 293 bytes; each directory 4 KiB allocated; exact primary/backup/export SHA-256 c62a7dd2a654e7c13fd283fe3b99df4fa957b9526f56183d3ac18d2603285cbd. Internal free 128 GiB, external 1.9 TiB at observation. No old data relocated.
- LaunchAgent com.arvectum.os.wsf-manual-backup, RunAtLoad, daily 21:00 host local, internal logs. Plist valid; launchd first run exited 0 and reported verified-current, 293 bytes. Backups also run before and after manual writes; before future governed updates use runbook. No recurring archive.
- Technical local session: no-session GET denied 401; authenticated /api/app/v1/manual-context HTTP 200, zero projects/notes and backup_status verified; missing CSRF write denied 403; export HTTP 200 byte-identical with both file copies; logout HTTP 200. This proves actual launched Workspace can access external backup for verified read. Command opening /manual-context in browser succeeded. No production business record created or human interaction inferred.

## Open acceptance / limitations

Pilot remains bounded to non-sensitive owner-entered working metadata, no personal/customer-confidential data or external ingestion. First genuine Owner project and note, revision/history/export and observed post-write backup from live BFF remain to be exercised. Full runtime restore/reboot resilience not proven. Actual scheduled job verified an already-created copy, not a new backup write from launchd; physical backup write/recovery was proven separately in operator/synthetic contexts. Owner daily-use feedback and retention review by 2026-12-17 remain open. No automated purge; no automatic renewal; no off-site recovery claim. Technical activation is not business adoption or P10.07/P10.10 completion.

Before any later governed deployment while active, require current-release manual-context backup PASS, independently of P7.03. To expand handling scope or connect email/CRM contacts, obtain separate review and approval.
