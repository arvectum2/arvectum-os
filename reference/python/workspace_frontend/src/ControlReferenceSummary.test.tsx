import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {ControlReferenceSummary} from "./ControlReferenceSummary";
import {LanguageProvider} from "./i18n";
const as_of="2026-11-17T10:00:00Z";
const base={derived:true,canonical_authority:false,organizational_authority_provided:false};
const crm={...base,company_control_coverage:"unknown",as_of,items:[{opportunity_id:"fixture",title:"Synthetic opportunity",party_name:"Synthetic party",next_action:"Reply",next_contact_at:null,status:"unscheduled",authority_provided:false}]};
const inbox={...base,coverage:"partial",pending_count:1,backup_status:"verified",sources:[{source_id:"PORT-007",state:"current-source-backed",freshness:"current-observation"},{source_id:"PORT-006",state:"reconciliation-required",freshness:"requires-refresh"}],items:[{id:"fixture",source_id:"PORT-007",repository:"arvectum2/data-platform",detected_at:as_of,state:"pending",canonical_authority:false}]};
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
const show=(deny=vi.fn())=>render(<LanguageProvider initialLanguage="ru"><ControlReferenceSummary onDenied={deny}/></LanguageProvider>);
const click=()=>fireEvent.click(screen.getByRole("button",{name:"Проверить рабочие сигналы"}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("reads only existing GET routes after explicit request and shows non-authoritative signals",async()=>{
 const fetchMock=vi.fn(async(input:RequestInfo|URL)=>response(String(input).endsWith("followups")?crm:inbox));
 vi.stubGlobal("fetch",fetchMock);show();
 expect(fetchMock).not.toHaveBeenCalled();click();
 await screen.findByRole("heading",{name:"Synthetic opportunity · Synthetic party"});
 await screen.findByText("Ожидают просмотра: 1");
 expect(screen.getByText("Свежие наблюдения: 1/2")).toBeTruthy();
 expect(screen.getByText(/PORT-006/)).toBeTruthy();
 expect(fetchMock.mock.calls.map(x=>x[0])).toEqual(["/api/app/v1/crm/followups","/api/app/v1/roadmap-inbox"]);
});
it("distinguishes unavailable from genuine empty partial source",async()=>{
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>String(input).endsWith("followups")?response({...crm,items:[]}):response({},503)));
 show();click();
 await screen.findByText(/В допущенной CRM нет открытых сделок/);
 await screen.findByText("Источник недоступен; состояние неизвестно.");
 expect(screen.queryByText(/Ожидают просмотра:/)).toBeNull();
});
it("clears previous data and notifies parent on revoked access",async()=>{
 let denied=false;const deny=vi.fn();
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>String(input).endsWith("followups")?response(crm):denied?response({},403):response(inbox)));
 show(deny);click();await screen.findByText("Ожидают просмотра: 1");
 denied=true;click();
 expect(screen.queryByText("Ожидают просмотра: 1")).toBeNull();
 await vi.waitFor(()=>expect(deny).toHaveBeenCalledTimes(1));
 expect(screen.queryByRole("heading",{name:"Synthetic opportunity · Synthetic party"})).toBeNull();
 expect(screen.queryByText("Ожидают просмотра: 1")).toBeNull();
});
it("rejects malformed, inconsistent or authority-bearing projections",async()=>{
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>response(String(input).endsWith("followups")?{...crm,canonical_authority:true}:{...inbox,pending_count:0})));
 show();click();await vi.waitFor(()=>expect(screen.getAllByText("Источник недоступен; состояние неизвестно.")).toHaveLength(2));
 expect(screen.queryByText("Ожидают просмотра: 0")).toBeNull();
});
