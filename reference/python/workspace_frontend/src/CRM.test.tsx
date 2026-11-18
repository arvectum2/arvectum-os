import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach,expect,it,vi } from "vitest";
import { CRM } from "./CRM";
import { LanguageProvider } from "./i18n";
const empty={party:[],contact:[],opportunity:[],interaction:[]};
const cat={projects:[],evidence_refs:[]};
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
function show(){render(<LanguageProvider initialLanguage="ru"><CRM csrfToken="fixture"/></LanguageProvider>);}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("denies default disabled and hides edit controls",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>response({},503)));show();
 await screen.findByRole("alert");
 expect(screen.queryByRole("button",{name:"Сохранить"})).toBeNull();
});
it("creates a counterparty through CSRF protected API and reads history",async()=>{
 const p={id:"PARTY-"+"a".repeat(32),name:"Synthetic",description:"Fixture",registry_ref:null,revision:1,recorded_at:"2026-11-17T10:00:00Z",authority_provided:false};
 let d:{party:unknown[],contact:unknown[],opportunity:unknown[],interaction:unknown[]}=empty;
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
  const path=String(input);
  if(path.endsWith("/catalog"))return response(cat);
  if(path.endsWith("/history"))return response([p]);
  if(path.endsWith("/submit")){
   expect(new Headers(init?.headers).get("X-Arvectum-CSRF")).toBe("fixture");
   const c=JSON.parse(String(init?.body));
   expect(c.entity).toBe("party");expect(c.expected_revision).toBe(0);expect(c.key).toMatch(/^[0-9a-f]{32}$/);
   expect(c.data.name).toBe(p.name);d={...empty,party:[p]};return response(p);
  }
  return response(d);
 }));show();
 fireEvent.change(await screen.findByLabelText("Название компании"),{target:{value:p.name}});
 fireEvent.change(screen.getByLabelText("Описание"),{target:{value:p.description}});
 fireEvent.click(screen.getByRole("button",{name:"Сохранить"}));
 await screen.findByRole("heading",{name:p.name});
 fireEvent.click(screen.getByRole("button",{name:"Версии"}));
 await screen.findByRole("heading",{name:"История версий"});
});
it("clears protected rows after access denial",async()=>{
 const mock=vi.fn(async(input:RequestInfo|URL)=>String(input).endsWith("/catalog")?response(cat):response({...empty,party:[{id:"p",name:"Private fixture",revision:1}]}));
 vi.stubGlobal("fetch",mock);show();await screen.findByRole("heading",{name:"Private fixture"});
 mock.mockImplementation(async()=>response({},403));
 fireEvent.click(screen.getByRole("button",{name:"Обновить"}));await screen.findByRole("alert");
 expect(screen.queryByRole("heading",{name:"Private fixture"})).toBeNull();
});

it("shows follow-up coordination without interpreting it as an obligation",async()=>{
 const row={opportunity_id:"fixture",party_name:"Synthetic",title:"Synthetic opportunity",next_action:"Respond",next_contact_at:"2026-11-17T10:00:00Z",status:"past_due"};
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
  const path=String(input);
  if(path.endsWith("/catalog"))return response(cat);
  if(path.endsWith("/followups"))return response({items:[row]});
  return response(empty);
 }));show();
 fireEvent.click(await screen.findByRole("button",{name:"Следующие контакты"}));
 await screen.findByRole("heading",{name:"Synthetic opportunity · Synthetic"});
 expect(screen.getByText("Просрочен контакт")).toBeTruthy();
 expect(screen.getByText("Координация сделок, не подтверждённые обязательства.")).toBeTruthy();
});

it("opens linked project opportunities and offers return to notes",async()=>{
 const project="PRJ-"+"a".repeat(32),other="PRJ-"+"b".repeat(32);
 const row={id:"OPP-a",title:"Linked opportunity",party_id:"PARTY-a",project_id:project,stage:"qualified",next_action:"Review",revision:1,authority_provided:false};
 window.history.replaceState(null,"","/crm?project_id="+project);
 try{
  const f=vi.fn(async(input:RequestInfo|URL)=>String(input).endsWith("/catalog")?response({...cat,projects:[{id:project,label:"Fixture project"},{id:other,label:"Other project"}],allowed_entities:["party","opportunity"]}):response({...empty,opportunity:[row,{...row,id:"OPP-b",title:"Other opportunity",project_id:other}]}));
  vi.stubGlobal("fetch",f);show();
  expect((await screen.findByRole("link",{name:"Заметки этого проекта"})).getAttribute("href")).toBe("/manual-context?project_id="+project);
  await screen.findByRole("heading",{name:row.title});
  expect(screen.queryByRole("heading",{name:"Other opportunity"})).toBeNull();
  expect(f).toHaveBeenCalledTimes(2);
 }finally{window.history.replaceState(null,"","/");}
});
it("invalid project links do not fall through to all CRM rows",async()=>{
 window.history.replaceState(null,"","/crm?project_id=invalid");
 try{
  vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>String(input).endsWith("/catalog")?response(cat):response({...empty,party:[{id:"p",name:"Unrelated party",revision:1}]})));
  show();
  await screen.findByText("Запрошенный проект недоступен. Выберите проект в списке.");
  expect(screen.queryByRole("heading",{name:"Unrelated party"})).toBeNull();
  expect((screen.getByRole("button",{name:"Следующие контакты"}) as HTMLButtonElement).disabled).toBe(true);
 }finally{window.history.replaceState(null,"","/");}
});
