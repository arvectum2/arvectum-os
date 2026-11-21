import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {CompanySourceWatch} from "./CompanySourceWatch";
import {LanguageProvider} from "./i18n";
import type {CompanySourceWatchCandidate} from "./f11Types";

const candidate:CompanySourceWatchCandidate={
  schema:"arvectum.company.source-watch-view/1",state:"current-observation",derived:true,
  canonical_authority:false,business_status_updated:false,organizational_authority_provided:false,
  source_as_of:"2026-11-20",scanned_at:"2026-11-21T12:17:55+00:00",report_name:"company-source-watch-20261121T121755534031Z.json",
  coverage:{projects:22,source_refs:35,os_exact_paths_delegated:5,additional_repositories:14,
    review_signals:{incomplete_source_evidence:10,observed_source_unchanged:5,unscoped_repo_activity_review:4,existing_os_collector_review_required:3}},
  projects:[{project:"Synthetic Company",review_signal:"incomplete_source_evidence"}, ...Array.from({length:21},(_,i)=>({project:`Fixture ${i}`,review_signal:"observed_source_unchanged"}))],
};
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const show=()=>render(<LanguageProvider initialLanguage="ru"><CompanySourceWatch/></LanguageProvider>);
it("shows 22 Company project signals without claiming a business-status update",async()=>{
  const mock=vi.fn(async(_input:RequestInfo|URL)=>new Response(JSON.stringify(candidate),{status:200}));vi.stubGlobal("fetch",mock);
  show();await screen.findByText(/22 проектов/);
  expect(screen.getByText(/Снимок бизнес-очереди от/)).toBeTruthy();
  expect(screen.getByText(/не утверждение завершения или смена бизнес-статуса/)).toBeTruthy();
  fireEvent.click(screen.getByText(/Сигналы по всем проектам/));
  expect(screen.getByText("Synthetic Company")).toBeTruthy();
  expect(mock).toHaveBeenCalledTimes(1);
  expect(String(mock.mock.calls[0][0])).toContain("/api/app/v1/company/source-watch");
});
it("does not show older evidence as fresh after read is denied",async()=>{
  const mock=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(candidate),{status:200}))
    .mockResolvedValueOnce(new Response("{}",{status:503}));vi.stubGlobal("fetch",mock);
  show();await screen.findByText(/22 проектов/);
  fireEvent.click(screen.getByRole("button",{name:"Перечитать отчёт"}));
  await screen.findByText(/Отчёт Company не допущен или недоступен/);
  expect(screen.queryByText(/22 проектов/)).toBeNull();
  expect(mock).toHaveBeenCalledTimes(2);
});
it("marks stale report and preserves unknown source status",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({...candidate,state:"stale"}),{status:200})));
  show();await screen.findByText(/Отчёт устарел/);
  expect(screen.getByText(/не подтверждает здоровье сборщика/)).toBeTruthy();
});
