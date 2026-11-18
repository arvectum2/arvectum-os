import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ManualContext } from "./ManualContext";
import { LanguageProvider } from "./i18n";
const empty={projects:[],notes:[]};
function response(body: unknown,status=200){return new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json"}});}
function show(){render(<LanguageProvider initialLanguage="ru"><ManualContext csrfToken="fixture-csrf"/></LanguageProvider>);}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("does not expose forms when pilot is disabled",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>response({},503)));show();
  await screen.findByRole("alert");
  expect(screen.queryByRole("button",{name:"Создать проект"})).toBeNull();
});
it("creates project and captures a linked note via protected API",async()=>{
  const p={id:"PRJ-"+"a".repeat(32),label:"Fixture project",kind:"customer"};
  const n={id:"NOTE-"+"b".repeat(32),title:"Fixture note",text:"Fixture body",project_id:p.id,revision:1,at:"2026-11-17T10:00:00Z"};
  let current:{projects:unknown[],notes:unknown[]}=empty;
  const mock=vi.fn(async(input: RequestInfo | URL,init?:RequestInit)=>{
    if(String(input).endsWith("/submit")){
      const cmd=JSON.parse(String(init?.body));
      expect(new Headers(init?.headers).get("X-Arvectum-CSRF")).toBe("fixture-csrf");
      expect(cmd.key).toMatch(/^[0-9a-f]{32}$/);
      if(cmd.operation==="project"){current={projects:[p],notes:[]};return response(p);}
      expect(cmd.payload.project_id).toBe(p.id);current={projects:[p],notes:[n]};return response(n);
    }
    return response(current);
  });
  vi.stubGlobal("fetch",mock);show();
  fireEvent.click(await screen.findByText("Добавить проект или заметку"));
  fireEvent.change(await screen.findByLabelText("Название проекта"),{target:{value:p.label}});
  fireEvent.click(screen.getByRole("button",{name:"Создать проект"}));
  await waitFor(()=>expect(screen.getAllByRole("option",{name:p.label})).toHaveLength(2));
  fireEvent.change(screen.getByLabelText("Заголовок"),{target:{value:n.title}});
  fireEvent.change(screen.getByLabelText("Заметка"),{target:{value:n.text}});
  fireEvent.change(screen.getByLabelText("Привязка к проекту"),{target:{value:p.id}});
  fireEvent.click(screen.getByRole("button",{name:"Сохранить заметку"}));
  await screen.findByText(n.title);
});
it("clears previous protected content on failed refresh",async()=>{
  vi.stubGlobal("fetch",vi.fn().mockImplementationOnce(async()=>response({projects:[],notes:[{id:"NOTE-x",title:"Private fixture",text:"Synthetic",project_id:null,revision:1,at:"now"}]})).mockImplementationOnce(async()=>response({},403)));
  show();await screen.findByText("Private fixture");
  fireEvent.click(screen.getByRole("button",{name:"Обновить"}));
  await screen.findByRole("alert");
  expect(screen.queryByText("Private fixture")).toBeNull();
});
