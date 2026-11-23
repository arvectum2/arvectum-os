import {contractDateFromCondition} from "./OwnerBusinessBrief";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {LanguageProvider} from "./i18n";
import {ExecutiveOverview} from "./ExecutiveOverview";
import fixture from "./__fixtures__/executive-preview.json";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const click=()=>{fireEvent.click(screen.getByRole("button",{name:"Обновить сводку"}));const toggle=screen.queryByRole("button",{name:"Проверочные данные и источники (для аудита)"});if(toggle)fireEvent.click(toggle);};
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
it("one explicit read of eight existing routes; no duplicate linked decision or historic authority",async()=>{
 const {f}=setup();expect(f).not.toHaveBeenCalled();click();
 await screen.findByText("Клиентский проект — сдать результат");
 expect(f).toHaveBeenCalledTimes(8);
 expect(screen.getByRole("link",{name:"Изменения ожидают просмотра"}).getAttribute("href")).toBe("/information-hub?view=changes");
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
 expect(f).toHaveBeenCalledTimes(8);
});

it("makes next checks visible without opening evidence and separates owner work from execution queue",async()=>{
 const {f}=setup();click();
 await screen.findByText("Пересмотр пилота");
 const titles=["Клиентский проект — сдать результат","Клиентский проект — оформить приёмку","Пересмотр пилота"];
 for(const title of titles){
  const row=screen.getByText(title).closest("details")!;
  expect(row.open).toBe(false);
  expect(row.querySelector("summary .exec-next-point")?.textContent).toContain("Проверить подтверждения и условия");
  expect(row.querySelector("summary")?.textContent).not.toContain("synthetic evidence");
 }
 expect(screen.getByText(/Прочитаны источники: 8\/8/)).toBeTruthy();
 expect(screen.getByText("Отдельная очередь исполнения, не реестр решений собственника.")).toBeTruthy();
 expect(screen.getByText("Контроль исполнения. Ответственная Position указана в основаниях; это не список личных поручений собственнику.")).toBeTruthy();
 expect(screen.queryByRole("button",{name:/утвердить|принять решение/i})).toBeNull();
 expect(f).toHaveBeenCalledTimes(8);
});
it("does not mistake a failed decision read for an unprepared decision",async()=>{
 const a=setup();a.fail("company-decision-reference",503);click();
 const label=await screen.findByText("Сведения о решении недоступны");
 expect(label.closest("summary")).toBeTruthy();
 expect(screen.getByText(/Прочитаны источники: 7\/8/)).toBeTruthy();
 expect(screen.queryByText("Решение готовится · не готово к утверждению")).toBeNull();
 expect(screen.getByText("Пересмотр пилота")).toBeTruthy();
});
it("preserves the preparing decision if linked work is unavailable without fabricating a task",async()=>{
 const a=setup("work");a.fail("company-control-reference",503);click();
 await screen.findByText(/Связанное решение пилота · Готовится/);
 expect(screen.getByText(/Связанная работа недоступна в текущей сводке: WORK-001/)).toBeTruthy();
 expect(screen.queryByText("Пересмотр пилота")).toBeNull();
 expect(screen.getByText(/Прочитаны источники: 2\/3/)).toBeTruthy();
});
it("distinguishes exact review deadline from conditional obligations without inferring completion",async()=>{
 vi.setSystemTime(new Date("2026-12-18T10:00:00Z"));
 try{
  setup();click();await screen.findByText("Пересмотр пилота");
  expect(screen.getAllByText("Контрольный срок наступил · состояние исполнения не подтверждено")).toHaveLength(1);
  const obligation=screen.getByText("Клиентский проект — сдать результат").closest("summary")!;
  expect(obligation.textContent).toContain("Срок / условие: По договорному сроку");
  expect(obligation.textContent).not.toContain("Контрольный срок наступил");
  expect(screen.getByText("Решение готовится · не готово к утверждению")).toBeTruthy();
 }finally{vi.useRealTimers();}
});

it("shows dated and unscheduled follow-ups without silently hiding the remaining queue",async()=>{
 const old=fixture["crm/followups"];
 const crm={...old,items:[
 {opportunity_id:"opp-a",title:"Тестовое обсуждение",party_name:"Компания А",next_action:"Уточнить потребность",next_contact_at:null,status:"unscheduled",authority_provided:false},
 {opportunity_id:"opp-b",title:"Тестовое предложение",party_name:"Компания Б",next_action:"Сверить ответ",next_contact_at:"2026-11-18T06:00:00Z",status:"past_due",authority_provided:false},
 {opportunity_id:"opp-c",title:"Тестовая встреча",party_name:"Компания В",next_action:"Подготовить материалы",next_contact_at:"2026-11-25T06:00:00Z",status:"scheduled",authority_provided:false},
 {opportunity_id:"opp-d",title:"Тестовая пауза",party_name:"Компания Г",next_action:"Проверить условие",next_contact_at:null,status:"paused",authority_provided:false}
 ]};
 const f=vi.fn(async(input:RequestInfo|URL)=>{
  const k=String(input).replace("/api/app/v1/","");
  return new Response(JSON.stringify(k==="crm/followups"?crm:fixture[k as keyof typeof fixture]),{status:200});
 });
 vi.stubGlobal("fetch",f);
 render(<LanguageProvider initialLanguage="ru"><ExecutiveOverview csrfToken="fixture"/></LanguageProvider>);
 click();
 expect((await screen.findAllByText("Компания А")).length).toBe(2);
 expect(screen.getByText("Дата не задана: 1 · Срок контакта прошёл: 1")).toBeTruthy();
 expect(screen.getByText("Дата не задана")).toBeTruthy();
 expect(screen.getByText(/Срок контакта прошёл ·/)).toBeTruthy();
 expect(screen.getByText(/Запланирован ·/)).toBeTruthy();
 expect(screen.getByRole("link",{name:"Открыть все контакты: 4"}).getAttribute("href")).toBe("/crm");
 expect(screen.queryByText("Компания Г")).toBeNull();
 expect(f).toHaveBeenCalledTimes(8);
});
it("distinguishes uncovered delegation and portfolio control from real technical evidence",async()=>{
 setup();click();await screen.findByText("Пересмотр пилота");
 expect(screen.getByText("Покрытие делегированной работы: не установлено.")).toBeTruthy();
 expect(screen.getByText(/Решения AC-405 о приоритетах и инвестициях не допущены/)).toBeTruthy();
 expect(screen.getAllByText("Ответственная Position: POS-002")).toHaveLength(2);
 expect(screen.getByText("В допущенной очереди нет следующих контактов.")).toBeTruthy();
 expect(screen.getByText("Сведения о сервисном сборе: Не установлено")).toBeTruthy();
 expect(screen.getByText(/Фактическое использование собственником, экономия времени и результативность AI не измеряются/)).toBeTruthy();
});
it("never treats a failed CRM read as an empty or zero follow-up queue",async()=>{
 const a=setup();a.fail("crm/followups",503);click();await screen.findByText("Пересмотр пилота");
 expect(screen.queryByText(/Дата не задана: 0/)).toBeNull();
 expect(screen.queryByText("В допущенной очереди нет следующих контактов.")).toBeNull();
 expect(screen.getByText(/Прочитаны источники: 7\/8/)).toBeTruthy();
});

it("shows admitted Position work separately, without a new owner decision or invented deadline",async()=>{
 const prior=fixture["company-control-reference"];
 const position_work=[
 {...prior.owner_action[0],id:"WORK-002",title:"Коммерческая квалификация",accountable_position:"POS-002",priority:"P1",control_state:"open",owner_action:"not_required",decision_ready:false,due_or_trigger:{kind:"none",value:null,source_ref:null}},
 {...prior.owner_action[0],id:"WORK-003",title:"Управленческие финансовые данные",accountable_position:"POS-005",priority:"P1",control_state:"open",owner_action:"not_required",decision_ready:false,due_or_trigger:{kind:"none",value:null,source_ref:null}}
 ];
 const f=vi.fn(async(input:RequestInfo|URL)=>{
  const k=String(input).replace("/api/app/v1/","");
  return new Response(JSON.stringify(k==="company-control-reference"?{...prior,position_work}:fixture[k as keyof typeof fixture]),{status:200});
 });
 vi.stubGlobal("fetch",f);
 render(<LanguageProvider initialLanguage="ru"><ExecutiveOverview csrfToken="fixture" mode="work"/></LanguageProvider>);
 click();await screen.findByText("Работы ответственных должностей");
 expect(screen.getByText("Коммерческая квалификация")).toBeTruthy();
 expect(screen.getByText("Управленческие финансовые данные")).toBeTruthy();
 expect(screen.getByText("WORK-002 · POS-002 · P1")).toBeTruthy();
 expect(screen.getAllByText("Срок не задан · состояние требует сверки")).toHaveLength(2);
 expect(screen.getByText("Пересмотр пилота")).toBeTruthy();
 expect(f).toHaveBeenCalledTimes(3);
});

it("finance structure shows a conditional calendar item and blocked calculations, not fabricated balances",async()=>{
 const a=setup("finance");click();
 await screen.findByRole("heading",{name:"Платёжный календарь"});
 for(const name of ["Деньги и движения","Расходы и лимиты","Прогноз ликвидности","Экономика проектов","Источники и контроль"])
  expect(screen.getByRole("heading",{name})).toBeTruthy();
 expect(screen.getByText("Дата не подтверждена")).toBeTruthy();
 expect(screen.getByText("Расчёт недоступен — недостаточно подтверждённых данных")).toBeTruthy();
 expect(screen.getByText("Условное поступление по контракту")).toBeTruthy();
 expect(screen.getAllByText("Не установлено").length).toBeGreaterThan(15);
 expect(screen.queryByRole("button",{name:/оплатить|сохранить|подключить/i})).toBeNull();
 expect(a.f).toHaveBeenCalledTimes(1);
 a.fail("company-finance-reference",403);click();
 await screen.findByRole("alert");
 expect(screen.queryByRole("heading",{name:"Платёжный календарь"})).toBeNull();
 expect(screen.queryByText("Условное поступление по контракту")).toBeNull();
});

it("reconciles admitted risk links and separates historical acts from Owner action",async()=>{
 const a=setup();click();await screen.findByText("Пересмотр пилота");
 expect(screen.getByText(/Исторические решения и согласования в допущенном реестре: 3/)).toBeTruthy();
 expect(screen.getByText(/Эскалации: сведения не допущены/)).toBeTruthy();
 expect(screen.getByText(/Исключения и инциденты: сведения не допущены/)).toBeTruthy();
 expect(screen.getAllByText(/Связь не подтверждает выполнение работы или закрытие риска/)).toHaveLength(3);
 expect(screen.getAllByText(/WORK-001 · Пересмотр пилота/).length).toBeGreaterThan(0);
 expect(screen.getAllByText(/Следующая проверка:/)).toHaveLength(3);
 expect(a.f).toHaveBeenCalledTimes(8);
 a.fail("company-control-reference",503);click();
 await screen.findAllByText(/Связанная запись не допущена или недоступна/);
 expect(screen.queryByText(/WORK-001 · Пересмотр пилота/)).toBeNull();
 a.fail("company-risk-reference",403);click();await screen.findByRole("alert");
 expect(screen.queryByText(/Исторические решения и согласования в допущенном реестре/)).toBeNull();
 expect(screen.queryByText(/Связь не подтверждает выполнение работы или закрытие риска/)).toBeNull();
});

it("shows the separately admitted dated project queue and clears it if source denied",async()=>{
 const a=setup();click();await screen.findAllByText("Synthetic held next action");
 expect(screen.getByText(/Снимок от 2026-11-20/)).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Подготовка · 0"}));
 expect(document.querySelector(".owner-queue")?.textContent).not.toContain("Synthetic held next action");
 fireEvent.click(screen.getByRole("button",{name:"Отложено · 1"}));
 expect(screen.getAllByText("Synthetic held next action").length).toBeGreaterThan(0);
 a.fail("company-owner-project-queue",403);click();await screen.findByRole("alert");
 expect(screen.queryByText("Synthetic held next action")).toBeNull();
});

it("places source-honest key signals above project detail and distinguishes unknown cash",async()=>{
 setup();click();await screen.findByRole("navigation",{name:"Главные показатели"});
 const panel=screen.getByRole("navigation",{name:"Главные показатели"});
 expect(panel.textContent).toContain("Доступные деньги");
 expect(panel.textContent).toContain("Не установлено");
 expect(panel.textContent).toContain("1 / 1");
 const obligations=document.getElementById("exec-obligations")!;
 const queue=document.getElementById("exec-projects")!;
 expect(Boolean(obligations.compareDocumentPosition(queue)&Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
 const finance=document.getElementById("exec-finance")!;
 expect(Boolean(finance.compareDocumentPosition(queue)&Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
});
it("does not invent zero totals when source unavailable",async()=>{
 const a=setup();a.fail("company-owner-project-queue",503);click();await screen.findByText("Пересмотр пилота");
 expect(screen.getByRole("link",{name:/Проекты и действия/}).textContent).toContain("Не установлено");
});
it("keeps every project accessible when list is compact",async()=>{
 const q=fixture["company-owner-project-queue"];
 const projects=Array.from({length:8},(_,i)=>({...q.projects[0],label:"Project "+i}));
 const items=projects.map((p,i)=>({...q.items[0],project:p.label,ref:"REF-"+i,action:"Action "+i}));
 const snapshot={...q,projects,items,counts:{...q.counts,projects:8,actions:8,queues:{...q.counts.queues,hold:8}}};
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
 const k=String(input).replace("/api/app/v1/","");
 return new Response(JSON.stringify(k==="company-owner-project-queue"?snapshot:fixture[k as keyof typeof fixture]),{status:200});
 }));
 render(<LanguageProvider initialLanguage="ru"><ExecutiveOverview csrfToken="fixture"/></LanguageProvider>);
 click();await screen.findByText("Показать все проекты по фильтру · 8");
 expect(document.querySelectorAll(".oq-project")).toHaveLength(6);
 fireEvent.click(screen.getByText("Показать все проекты по фильтру · 8"));
 expect(document.querySelectorAll(".oq-project")).toHaveLength(8);
 fireEvent.change(screen.getByRole("combobox",{name:"Проект"}),{target:{value:"Project 7"}});
 expect(document.querySelectorAll(".oq-project")).toHaveLength(1);
 expect(document.querySelector(".oq-project[open]")?.textContent).toContain("REF-7");
 fireEvent.click(screen.getByRole("button",{name:"Подготовка · 0"}));
 expect(screen.getByText(/По выбранным условиям действий нет/)).toBeTruthy();
});

it("keeps technical original wording in disclosure while localizing visible action",async()=>{
 const q=fixture["company-owner-project-queue"];
 const snapshot={...q,items:[{...q.items[0],action:"Read-only сверка фактических receipts"}]};
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
  const k=String(input).replace("/api/app/v1/","");
  return new Response(JSON.stringify(k==="company-owner-project-queue"?snapshot:fixture[k as keyof typeof fixture]),{status:200});
 }));
 render(<LanguageProvider initialLanguage="ru"><ExecutiveOverview csrfToken="fixture"/></LanguageProvider>);
 click();await screen.findByText(/Следующее по списку/);
 expect(document.querySelector(".oq-project>summary")?.textContent).toContain("Сверка без изменения данных фактических подтверждений");
 expect(document.querySelector(".oq-project>summary")?.textContent).not.toContain("receipts");
 fireEvent.click(document.querySelector(".oq-project>summary")!);
 expect(screen.getByText("Read-only сверка фактических receipts").closest("details")?.open).toBe(false);
});

it("opens with actionable company information, technical registers concealed",async()=>{
 const a=setup();
 fireEvent.click(screen.getByRole("button",{name:"Обновить сводку"}));
 await screen.findByRole("region",{name:"Состояние бизнеса"});
 expect(screen.getByText("Что происходит с компанией")).toBeTruthy();
 expect(screen.getByText("Клиентский проект: сдать результат")).toBeTruthy();
 expect(screen.getByText("Продажи: следующий контакт")).toBeTruthy();
 expect(screen.getByText("Деньги: чего не хватает для решения")).toBeTruthy();
 const technical=document.querySelector(".owner-evidence-hidden");
 expect(technical?.getAttribute("aria-hidden")).toBe("true");
 expect(screen.getByRole("button",{name:"Проверочные данные и источники (для аудита)"}).getAttribute("aria-expanded")).toBe("false");
 expect(a.f).toHaveBeenCalledTimes(8);
});
it("preserves all 22 project contours and 51 references behind a readable front page",async()=>{
 const base=fixture["company-owner-project-queue"];
 const projects=["Музей Хлеба",...Array.from({length:21},(_,i)=>"Project "+i)].map(label=>({...base.projects[0],label}));
 const items=Array.from({length:51},(_,i)=>({...base.items[0],project:projects[i%22].label,ref:"SYNTH-"+i,action:"Synthetic action "+i}));
 const sample={...base,projects,items,counts:{...base.counts,projects:22,actions:51,queues:{...base.counts.queues,hold:51}}};
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
  const k=String(input).replace("/api/app/v1/","");
  return new Response(JSON.stringify(k==="company-owner-project-queue"?sample:fixture[k as keyof typeof fixture]),{status:200});
 }));
 render(<LanguageProvider initialLanguage="ru"><ExecutiveOverview csrfToken="fixture"/></LanguageProvider>);
 fireEvent.click(screen.getByRole("button",{name:"Обновить сводку"}));
 await screen.findByRole("button",{name:"Показать остальные направления (16)"});
 expect(document.querySelectorAll(".owner-business-project")).toHaveLength(6);
 fireEvent.click(screen.getByRole("button",{name:"Показать остальные направления (16)"}));
 expect(document.querySelectorAll(".owner-business-project")).toHaveLength(22);
 expect(document.querySelector(".owner-business-project summary")?.textContent).toContain("Результат не указан в управленческой сводке");
 fireEvent.click(screen.getByRole("button",{name:"Проверочные данные и источники (для аудита)"}));
 expect(document.querySelector(".owner-evidence-hidden")).toBeNull();
 expect(screen.getByText("Все · 51")).toBeTruthy();
});

it("shows a signed-contract calendar deadline without treating conditional acceptance as a date",()=>{
 expect(contractDateFromCondition("По 07.12.2026 включительно (договорная календарная дата)","ru-RU")).toContain("7 декабря 2026");
 expect(contractDateFromCondition("Не более 3 рабочих дней с даты окончания срока услуг","ru-RU")).toBeNull();
 expect(contractDateFromCondition("По 31.02.2026 включительно","ru-RU")).toBeNull();
});


it("keeps the business briefing visible without expanding the technical evidence",async()=>{
 const a=setup();a.fail("company-owner-project-queue",503);
 fireEvent.click(screen.getByRole("button",{name:"Обновить сводку"}));
 await screen.findByText("Что происходит с компанией");
 expect(screen.getByRole("region",{name:"Состояние бизнеса"}).closest("details")).toBeNull();
 expect(screen.getByText(/Прочитано источников: 7\/8/)).toBeTruthy();
 expect(screen.getByText(/Не все источники доступны/)).toBeTruthy();
 expect(document.querySelector(".owner-evidence-hidden")?.getAttribute("aria-hidden")).toBe("true");
 expect(screen.getByText("Клиентский проект: сдать результат")).toBeTruthy();
 expect(a.f).toHaveBeenCalledTimes(8);
});


it("provides a recovery action after session authorization is lost",async()=>{
 const a=setup();a.fail("company-owner-project-queue",401);
 fireEvent.click(screen.getByRole("button",{name:"Обновить сводку"}));
 const alert=await screen.findByRole("alert");
 expect(alert.textContent).toContain("Обновите страницу для восстановления сеанса");
 expect(screen.queryByText("Пересмотр пилота")).toBeNull();
 expect(document.querySelector(".owner-evidence-hidden")?.getAttribute("aria-hidden")).toBe("true");
});
