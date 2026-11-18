import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {LanguageProvider} from "./i18n";
import {FinanceReference} from "./FinanceReference";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const keys="available_cash_fact_ref material_due_outflows material_receivables material_payables recurring_cost_signal expected_outflows approved_not_yet_incurred_exposure procurement_cash_gap_cases mandatory_payment_attention actual_receipts project_profitability".split(" ");
const data={schema:"arvectum.workspace.company-finance-reference/1",coverage:"partial",derived:true,canonical_authority:false,organizational_authority_provided:false,payment_authority:false,position:"POS-005",liquidity_status:"unknown",decision_readiness:"blocked_by_missing_financial_evidence",report_as_of:"2026-11-18T05:00:00Z",facts:Object.fromEntries(keys.map(k=>[k,{status:"unknown",value:null}])),conditional_inflow:{basis:"contractual_conditional",contract_price_rub:"123.45",expected_available_cash_rub:null,receivable_confirmed:false,actual_receipt_confirmed:false,advance_provided:false,timing_condition:"After acceptance",source_refs:["fixture"],linked_obligations:["OBL-001","OBL-002"]},unknowns:["fixture"],next_control_point:"Review"};
it("displays conditional price and unknown facts; rejects fabricated cash",async()=>{
 let current:unknown=data;
 const f=vi.fn(async()=>new Response(JSON.stringify(current)));vi.stubGlobal("fetch",f);
 render(<LanguageProvider initialLanguage="ru"><FinanceReference csrfToken="fixture"/></LanguageProvider>);
 expect(f).not.toHaveBeenCalled();fireEvent.click(screen.getByRole("button",{name:"Прочитать финансовую сводку"}));
 await screen.findByRole("heading",{name:"Условное поступление по контракту"});expect(screen.getAllByText("Не установлено")).toHaveLength(11);
 current={...data,facts:{...data.facts,available_cash_fact_ref:{status:"current",value:0}}};
 fireEvent.click(screen.getByRole("button",{name:"Прочитать финансовую сводку"}));await screen.findByRole("alert");expect(screen.queryByRole("heading",{name:"Условное поступление по контракту"})).toBeNull();
});
