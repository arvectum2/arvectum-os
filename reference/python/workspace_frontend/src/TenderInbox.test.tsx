import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {TenderInbox} from "./TenderInbox";
import {LanguageProvider} from "./i18n";
const group={id:"TENDERGROUP-"+"a".repeat(32),case_ref:"fixture-case",run_ref:"fixture-run",project_id:"PRJ-"+"b".repeat(32),event_ids:["event1","event2"],review_signal:true,revision:2,state:"pending",reviewed_at:null};
const observation={state:"observed",since:"2026-11-16T10:00:00Z",until:"2026-11-17T10:00:00Z",checked_at:"2026-11-17T10:01:00Z"};
const record={coverage:"partial",pending_count:1,backup_status:"verified",groups:[group],events:[{id:"event1",kind:"analysis_completed",occurred_at:"2026-11-17T09:00:00Z"},{id:"event2",kind:"review_required",occurred_at:"2026-11-17T09:01:00Z"}],observation};
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
function show(){render(<LanguageProvider initialLanguage="ru"><TenderInbox csrfToken="fixture"/></LanguageProvider>);fireEvent.click(screen.getByRole("button",{name:"Открыть события закупок"}));}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("groups two source events, reviews exact revision, preserves history",async()=>{
 let d=record;
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
  if(String(input).endsWith("/review")){
   expect(new Headers(init?.headers).get("X-Arvectum-CSRF")).toBe("fixture");
   const b=JSON.parse(String(init?.body));expect(b.item_id).toBe(group.id);expect(b.expected_revision).toBe(2);
   d={...record,pending_count:0,groups:[{...group,state:"reviewed",revision:3}]};
   return response({status:"saved",backup_status:"verified"});
  }
  return response(d);
 }));
 show();await screen.findByRole("heading",{name:"Требуется просмотр анализа"});
 expect(screen.getByText(/Связанных событий: 2/)).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Просмотрено"}));await screen.findByText("Групп к просмотру: 0");
 expect(screen.queryByRole("heading",{name:"Требуется просмотр анализа"})).toBeNull();
 fireEvent.click(screen.getByLabelText("Показать обработанные закупки"));await screen.findByRole("heading",{name:"Требуется просмотр анализа"});
});
it("shows overflow without treating previous work as closed",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>response({...record,observation:{...observation,state:"overflow"}})));
 show();await screen.findByText(/Слишком много событий/);
 expect(screen.getByText("Групп к просмотру: 1")).toBeTruthy();
});
it("clears protected records after access denial",async()=>{
 const f=vi.fn(async()=>response(record));vi.stubGlobal("fetch",f);show();
 await screen.findByRole("heading",{name:"Требуется просмотр анализа"});
 f.mockImplementation(async()=>response({},403));
 fireEvent.click(screen.getByRole("button",{name:"Обновить события закупок"}));
 await screen.findByRole("alert");expect(screen.queryByRole("heading",{name:"Требуется просмотр анализа"})).toBeNull();
});
it("does not show an empty-success state when source is not activated",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>response({},503)));show();
 await screen.findByRole("alert");
 expect(screen.queryByRole("button",{name:"Получить события за 24 часа"})).toBeNull();
});
