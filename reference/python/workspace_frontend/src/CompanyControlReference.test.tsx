import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {LanguageProvider} from "./i18n";
import {CompanyControlReference} from "./CompanyControlReference";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const fixture={coverage:"partial",derived:true,canonical_authority:false,organizational_authority_provided:false,owner_action:[{id:"WORK-001",title:"Fixture review",accountable_position:"POS-001",decision_ready:false,canonical_authority:false,priority:"P1",control_state:"open",evidence_as_of:"2026-11-17T12:00:00Z",next_control_point:"Review",source_refs:["fixture"],due_or_trigger:{kind:"exact",value:"2026-12-17T09:35:36Z"}}]};
it("reads only on request and hides previous record on denial",async()=>{
 let denied=false;
 const fetchMock=vi.fn(async()=>new Response(JSON.stringify(denied?{}:fixture),{status:denied?503:200}));
 vi.stubGlobal("fetch",fetchMock);
 render(<LanguageProvider initialLanguage="ru"><CompanyControlReference csrfToken="fixture"/></LanguageProvider>);
 expect(fetchMock).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole("button",{name:"Прочитать реестр работ"}));
 await screen.findByRole("heading",{name:"WORK-001 · Fixture review"});
 denied=true;fireEvent.click(screen.getByRole("button",{name:"Прочитать реестр работ"}));
 await screen.findByRole("alert");
 expect(screen.queryByRole("heading",{name:"WORK-001 · Fixture review"})).toBeNull();
});
