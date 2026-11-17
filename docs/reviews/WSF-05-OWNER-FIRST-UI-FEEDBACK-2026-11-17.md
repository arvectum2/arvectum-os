# WSF-05 — first owner usability feedback and correction

Date: 2026-11-17
Status: implementation candidate, not yet deployed or accepted.

Genuine owner feedback after seeding 12 projects and 12 notes: “пока в Workspace очень много лишней технической информации, и не понятно, где найти полезную и нужную информацию”.
This is negative usability evidence, not an acceptance PASS. The existing main route foregrounds technical attention signals, eight action links and multiple overlapping product/materials views while the actual working context is a nested menu item. Source-code inspection, not screenshot-based visual audit.

## Bounded correction
- Default Home: protected existing manual-context read; customer projects first, products/internal directions second; name search, last note title, short summary and direct selected-project route. Source tail and repetitive AI provenance prefix are suppressed only in the explicitly marked initial note preview; original note remains intact. No new source access, AI authority, task inference, data writes or persistence.
- Five primary navigation entries: Home, Projects (actual manual-context), Documents (company materials), Arvectum AI and Settings. Existing technical task queue, repository roadmaps, source synchronization, generated documents and advanced search remain accessible via Settings. Existing direct routes remain supported.
- Project links open selected project; notes above entry forms; note history and export unchanged.
- Unknown/unavailable context remains explicit; backup failures visible, not healthy by default. No synthetic totals, claims of actual owner attention, financials, deadlines or inbox events. This is a first simplified overview, not completed AC-406 Mission Control. Genuine obligations, required decisions and delegated work require verified sources and distinct authority.

Exact UI candidate p10.09.6; assets commit 1fd2d0ec570266d8ce6d9467a0ec20573b39bfd1; 64/64 SPA tests PASS after fixing two old navigation-journey expectations, typecheck, build, storage guard and asset pin PASS. Dist SHA-256 89f2e3a7b4fa78e0e6f02fb085f60a8e902a7dec7446a44f9ae7e1681b556c9d. Actual live UI and owner acceptance pending. No pilot reset, additional operation grants, new data stores or infrastructure. Before deployment, run active pilot backup as well as P7.06 preflight. Prior live release remains p10.09.5.

Acceptance: owner can locate an existing client/product project and its current working note from Home within two clicks and without reading technical terms, and can still access technical details when deliberately requested. Check with genuine owner feedback before broadening CRM/integrations.
