import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {RoadmapInbox} from "./RoadmapInbox";
import {LanguageProvider} from "./i18n";
const r={id:"INBOX-"+"a".repeat(32),source_id:"COMPANY",repository:"arvectum2/arvectum-company",path:"docs/roadmap/ROADMAP.md",observed:{commit_sha:"b".repeat(40)},previous:{commit_sha:"a".repeat(40)},detected_at:"2026-11-17T10:00:00Z",state:"pending",revision:1};
const d={coverage:"partial",pending_count:1,backup_status:"verified",items:[r],sources:[]};
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
function show(){render(<LanguageProvider initialLanguage="ru"><RoadmapInbox csrfToken="fixture"/></LanguageProvider>);}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("opens a change, authenticates review, retains reviewed history",async()=>{
 let current=d;
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
  if(String(input).endsWith("/review")){
   expect(new Headers(init?.headers).get("X-Arvectum-CSRF")).toBe("fixture");
   const b=JSON.parse(String(init?.body));expect(b.item_id).toBe(r.id);expect(b.expected_revision).toBe(1);
   current={...d,pending_count:0,items:[{...r,state:"reviewed",revision:2}]};
   return response({status:"saved",backup_status:"verified"});
  }
  return response(current);
 }));
 show();fireEvent.click(screen.getByRole("button",{name:"Открыть очередь изменений"}));
 await screen.findByRole("heading",{name:r.repository});
 expect(screen.getByRole("link",{name:"Новая версия"}).getAttribute("href")).toContain("b".repeat(40));
 fireEvent.click(screen.getByRole("button",{name:"Просмотрено"}));
 await screen.findByText("Ожидают просмотра: 0");
 expect(screen.queryByRole("heading",{name:r.repository})).toBeNull();
 fireEvent.click(screen.getByLabelText("Показать обработанные"));await screen.findByRole("heading",{name:r.repository});
});
it("does not retain records after revoked access",async()=>{
 const f=vi.fn(async()=>response(d));vi.stubGlobal("fetch",f);show();
 fireEvent.click(screen.getByRole("button",{name:"Открыть очередь изменений"}));
 await screen.findByRole("heading",{name:r.repository});
 f.mockImplementation(async()=>response({},403));fireEvent.click(screen.getByRole("button",{name:"Обновить очередь"}));
 await screen.findByRole("alert");expect(screen.queryByRole("heading",{name:r.repository})).toBeNull();
});
