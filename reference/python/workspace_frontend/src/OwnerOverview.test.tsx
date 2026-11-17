import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { OwnerOverview } from "./OwnerOverview";
import { LanguageProvider } from "./i18n";
const p={id:"PRJ-"+"a".repeat(32),label:"Клиентский проект",kind:"customer"};
const q={id:"PRJ-"+"b".repeat(32),label:"Внутренний продукт",kind:"internal"};
const note={id:"NOTE-"+"c".repeat(32), title:"Текущий ориентир", text:"Сводка подготовлена AI по прямому поручению собственника 17.11.2026; рабочая интерпретация, не новый канонический факт или решение. Подготовить макет. Источник: tech-sha-123",project_id:p.id,at:"2026-11-17T10:00:00Z"};
function show(){render(<LanguageProvider initialLanguage="ru"><OwnerOverview/></LanguageProvider>);}
const response=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{"Content-Type":"application/json"}});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("shows actual projects first, removes technical source tail from summary, and deep-links",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>response({projects:[p,q],notes:[note],backup_status:"verified"})));
  show();
  const client=await screen.findByRole("heading",{name:p.label});
  expect(screen.getByRole("heading",{name:"Клиентские проекты"})).toBeTruthy();
  expect(screen.getByRole("heading",{name:q.label})).toBeTruthy();
  const card=client.closest("article")!;
  expect(within(card).getByText("Подготовить макет.")).toBeTruthy();
  expect(within(card).getByRole("link",{name:"Открыть проект"}).getAttribute("href")).toBe("/manual-context?project="+p.id);
  expect(screen.queryByText(/tech-sha-123/)).toBeNull();
  fireEvent.change(screen.getByRole("searchbox"),{target:{value:"внутренний"}});
  expect(screen.queryByRole("heading",{name:p.label})).toBeNull();
  expect(screen.getByRole("heading",{name:q.label})).toBeTruthy();
});
it("does not claim an empty portfolio after a failed refresh",async()=>{
  vi.stubGlobal("fetch",vi.fn().mockImplementationOnce(async()=>response({projects:[p],notes:[note],backup_status:"verified"})).mockImplementationOnce(async()=>response({},403)));
  show();
  await screen.findByRole("heading",{name:p.label});
  fireEvent.click(screen.getByRole("button",{name:"Обновить"}));
  await screen.findByRole("alert");
  expect(screen.queryByRole("heading",{name:p.label})).toBeNull();
  expect(screen.queryByText("Нет проектов по этому запросу.")).toBeNull();
});
