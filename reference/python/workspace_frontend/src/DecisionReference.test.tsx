import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {LanguageProvider} from "./i18n";
import {DecisionReference} from "./DecisionReference";
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const base={title:"Fixture",capacity:"Owner",authority_basis:"fixture",constraints:"No effect",decision_ready:false,current_applicability:"unknown"};
const data={schema:"arvectum.workspace.company-decision-reference/1",coverage:"partial",derived:true,canonical_authority:false,organizational_authority_provided:false,items:[...([1,2,3].map(i=>({...base,id:"DEC-00"+i,kind:"decision",position:"POS-001",question:"Review",review_trigger:"Fixture trigger",recorded_state:i===3?"preparing":"decided",recorded_outcome:i===3?"none":"approve_with_conditions",act_ref:i===3?null:"fixture",linked_work:i===3?"WORK-001":null,review_due_at:i===3?"2026-12-17T09:35:36Z":null}))),{...base,id:"APR-001",kind:"approval",domain:"arvectum_os",recorded_state:"approved",scope:"Read",effective_period:"Fixture period",act_ref:"fixture"}]};
it("separates pending and historic acts and clears on denial",async()=>{
 let denied=false;const fetchMock=vi.fn(async()=>new Response(JSON.stringify(denied?{}:data),{status:denied?403:200}));
 vi.stubGlobal("fetch",fetchMock);render(<LanguageProvider initialLanguage="ru"><DecisionReference csrfToken="fixture"/></LanguageProvider>);
 expect(fetchMock).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole("button",{name:"Прочитать реестр решений"}));
 await screen.findByRole("heading",{name:"DEC-003 · Fixture"});
 expect(screen.getByText("Не готово к решению; результат не принят.")).toBeTruthy();
 expect(screen.getByRole("heading",{name:"APR-001 · Fixture"})).toBeTruthy();
 denied=true;fireEvent.click(screen.getByRole("button",{name:"Прочитать реестр решений"}));
 await screen.findByRole("alert");expect(screen.queryByRole("heading",{name:"APR-001 · Fixture"})).toBeNull();
});
