import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {LanguageProvider} from "./i18n";
import {ProcurementReference} from "./ProcurementReference";
const row={deal_id:"DL-fixture",procurement_number:"0123456789012345678",workflow_status:"POST_SUBMISSION",updated_at:"2026-11-17T12:00:00Z",recorded_decision:null,recommendation:{ref:"SCR-fixture",value:"GO",at:"2026-11-17T12:00:00Z"},submission:null,outcome:null};
const view={schema:"arvectum.workspace.internal-procurement-reference/1",source_release:"a".repeat(40),project_id:"PRJ-"+"b".repeat(32),observed_at:row.updated_at,coverage:"admitted-identity-set-only",canonical_authority:false,items:[row]};
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
function show(){render(<LanguageProvider initialLanguage="ru"><ProcurementReference csrfToken="fixture"/></LanguageProvider>);}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("only fetches explicitly and separates advisory recommendation from a missing human decision",async()=>{
 const f=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
  expect(String(input)).toBe("/api/app/v1/procurement-reference");
  expect(init?.method).toBe("POST");expect(new Headers(init?.headers).get("X-Arvectum-CSRF")).toBe("fixture");
  expect(init?.body).toBeUndefined();return response(view);
 });
 vi.stubGlobal("fetch",f);show();expect(f).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole("button",{name:"Получить портфель закупок"}));
 await screen.findByRole("heading",{name:row.procurement_number});
 expect(screen.getByText(/Зафиксированное решение: Нет подтверждённой записи/)).toBeTruthy();
 expect(screen.getByText(/Рекомендация системы: GO/)).toBeTruthy();
 expect(screen.getByText(/Запись подачи: Нет сведений/)).toBeTruthy();
 fireEvent.change(screen.getByLabelText("Фильтр закупок"),{target:{value:"submitted"}});
 expect(screen.queryByRole("heading",{name:row.procurement_number})).toBeNull();
});
it("hides previously visible private records after denied refresh",async()=>{
 const f=vi.fn(async()=>response(view));vi.stubGlobal("fetch",f);show();
 fireEvent.click(screen.getByRole("button",{name:"Получить портфель закупок"}));
 await screen.findByRole("heading",{name:row.procurement_number});
 f.mockImplementation(async()=>response({},503));
 fireEvent.click(screen.getByRole("button",{name:"Получить портфель закупок"}));
 await screen.findByRole("alert");expect(screen.queryByRole("heading",{name:row.procurement_number})).toBeNull();
});
