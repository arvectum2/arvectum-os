import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {MissionControl} from "./MissionControl";
import {LanguageProvider} from "./i18n";
const p={id:"PRJ-"+"a".repeat(32),label:"Fixture project",kind:"customer"};
const data={manual_context:{projects:[p],notes:[]},sections:[{id:"cash-commitments",state:"unknown",missing_source:"finance"}],pilot_review:{due_at:"2026-12-17T09:35:36Z",decision_ready:false}};
const response=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
function show(){render(<LanguageProvider initialLanguage="ru"><MissionControl/></LanguageProvider>);}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("shows actual review trigger, unknown sources and project timeline",async()=>{
 vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>String(input).endsWith("/timeline")?response({project:p,events:[{kind:"note-captured",at:"2026-11-17T10:00:00Z",record_id:"fixture",title:"Actual working observation",text:"Fixture details"}]}):response(data)));
 show();await screen.findByText(/Пересмотр пилота Workspace/);
 expect(screen.getByText(/Нет подключённого актуального источника/)).toBeTruthy();
 fireEvent.change(screen.getByLabelText("Проект"),{target:{value:p.id}});
 await screen.findByRole("heading",{name:"Actual working observation"});
});
it("clears previous view when access revoked",async()=>{
 const mock=vi.fn(async()=>response(data));vi.stubGlobal("fetch",mock);show();
 await screen.findByText(/Пересмотр пилота Workspace/);mock.mockImplementation(async()=>response({},403));
 fireEvent.click(screen.getByRole("button",{name:"Обновить"}));await screen.findByRole("alert");
 expect(screen.queryByText(/Пересмотр пилота Workspace/)).toBeNull();
});
