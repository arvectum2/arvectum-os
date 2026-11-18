import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {LanguageProvider} from "./i18n";
import {ExecutiveOverview} from "./ExecutiveOverview";
import fixture from "./__fixtures__/executive-preview.json";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const click=()=>fireEvent.click(screen.getByRole("button",{name:"Обновить сводку"}));
function setup(mode:"overview"|"work"|"finance"="overview"){
 let bad="",code=503;
 const f=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
  const k=String(input).replace("/api/app/v1/","");
  expect(Object.hasOwn(fixture,k)).toBe(true);
  expect(init?.method).toBe(k.startsWith("company-")?"POST":"GET");
  expect(init?.body).toBeUndefined();
  if(k.startsWith("company-"))expect(new Headers(init?.headers).get("X-Arvectum-CSRF")).toBe("fixture");
  return new Response(JSON.stringify(k===bad?{}:fixture[k as keyof typeof fixture]),{status:k===bad?code:200});
 });
 vi.stubGlobal("fetch",f);
 render(<LanguageProvider initialLanguage="ru"><ExecutiveOverview csrfToken="fixture" mode={mode}/></LanguageProvider>);
 return {f,fail:(k:string,n:number)=>{bad=k;code=n;}};
}
it("one explicit read of seven existing routes; no duplicate linked decision or historic authority",async()=>{
 const {f}=setup();expect(f).not.toHaveBeenCalled();click();
 await screen.findByText("Клиентский проект — сдать результат");
 expect(f).toHaveBeenCalledTimes(7);
 expect(screen.getByText("Пересмотр пилота")).toBeTruthy();
 expect(screen.queryByText("Связанное решение пилота")).toBeNull();
 expect(screen.queryByText("Историческое решение 1")).toBeNull();
 expect(screen.getByText(/Цена контракта · поступление условное/)).toBeTruthy();
 expect(screen.getByText("Банк и бухгалтерия не подключены")).toBeTruthy();
 expect(screen.getByText("Операционная очередь: 0")).toBeTruthy();
});
it("unavailable source independent, then denial clears all previously available data",async()=>{
 const a=setup();click();await screen.findByText("Пересмотр пилота");
 a.fail("company-finance-reference",503);click();
 await screen.findByText("Пересмотр пилота");
 expect(screen.getByText("Недоступно")).toBeTruthy();expect(screen.queryByText(/Цена контракта · поступление условное/)).toBeNull();
 a.fail("company-risk-reference",403);click();await screen.findByRole("alert");
 expect(screen.queryByText("Пересмотр пилота")).toBeNull();expect(screen.queryByText("Клиентский проект — сдать результат")).toBeNull();
});
it("finance route reads finance only and work route is separately scoped",async()=>{
 const a=setup("finance");click();await screen.findByText(/Цена контракта · поступление условное/);
 expect(a.f).toHaveBeenCalledTimes(1);
 cleanup();vi.unstubAllGlobals();
 const b=setup("work");click();await screen.findByText("Пересмотр пилота");
 await waitFor(()=>expect(b.f).toHaveBeenCalledTimes(3));
 expect(screen.queryByRole("heading",{name:"Финансы"})).toBeNull();
 expect(screen.queryByRole("heading",{name:"Риски"})).toBeNull();
});
it("reports eight current sources and separately preserves two excluded historical locators",async()=>{
 const active=["COMPANY","OS","PORT-001","PORT-002","PORT-003","PORT-004","PORT-007","PORT-008"];
 const old=fixture["roadmap-inbox"];
 const source=(source_id:string)=>({source_id,state:"current-source-backed",freshness:"current-observation"});
 const inbox={...old,sources:active.map(source),excluded_sources:["PORT-005","PORT-006"].map(source),
  items:[],pending_count:0,collector:{last_service_scan_at:"2026-11-18T15:00:00Z",last_verified_at:"2026-11-18T15:00:01Z",
   run_state:"verified",expires_at:"2026-12-17T09:35:36Z",next_window_at:"2026-11-18T18:00:00Z",
   release_sha:"a".repeat(40),event_count:20,bytes:10000,capacity_warning:false}};
 const f=vi.fn(async(input:RequestInfo|URL)=>{
  const k=String(input).replace("/api/app/v1/","");
  return new Response(JSON.stringify(k==="roadmap-inbox"?inbox:fixture[k as keyof typeof fixture]),{status:200});
 });
 vi.stubGlobal("fetch",f);
 render(<LanguageProvider initialLanguage="ru"><ExecutiveOverview csrfToken="fixture" mode="overview"/></LanguageProvider>);
 click();
 expect(await screen.findByText(/Актуальные сохранённые наблюдения: 8\/8/)).toBeTruthy();
 expect(screen.getByText(/Исключено из мониторинга: 2/)).toBeTruthy();
 expect(screen.getByText(/Локальный сборщик/)).toBeTruthy();
 expect(f).toHaveBeenCalledTimes(7);
});
