import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {LanguageProvider} from "./i18n";
import {RiskReference} from "./RiskReference";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const data={schema:"arvectum.workspace.company-risk-reference/1",coverage:"partial",derived:true,canonical_authority:false,organizational_authority_provided:false,items:[1,2,3].map((i)=>({id:"RSK-00"+i,title:"Fixture",position:["POS-006","POS-004","POS-002"][i-1],priority:i===3?"P0":"P1",recorded_state:"active",response_intent:"reduce",risk_accepted:false,owner_attention:"not_required",likelihood:"unknown",current_applicability:"unknown",risk_statement:"Fixture risk",residual_exposure:"Fixture exposure",control_evidence:"Partial",next_control_point:"Review",review_trigger:"Next control",source_refs:["fixture"],linked_work:["WORK-001"]}))};
it("reads exact risk references on request and clears on denial",async()=>{
 let denied=false;
 const f=vi.fn(async()=>new Response(JSON.stringify(denied?{}:data),{status:denied?403:200}));vi.stubGlobal("fetch",f);
 render(<LanguageProvider initialLanguage="ru"><RiskReference csrfToken="fixture"/></LanguageProvider>);
 expect(f).not.toHaveBeenCalled();fireEvent.click(screen.getByRole("button",{name:"Прочитать реестр рисков"}));
 await screen.findByRole("heading",{name:"RSK-003 · Fixture"});expect(screen.getByText("POS-002 · P0 · Открытый риск")).toBeTruthy();
 denied=true;fireEvent.click(screen.getByRole("button",{name:"Прочитать реестр рисков"}));await screen.findByRole("alert");expect(screen.queryByRole("heading",{name:"RSK-003 · Fixture"})).toBeNull();
});
