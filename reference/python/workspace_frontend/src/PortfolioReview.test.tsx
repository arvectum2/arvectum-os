import {cleanup,render,screen} from "@testing-library/react";
import {afterEach,expect,it} from "vitest";
import {LanguageProvider} from "./i18n";
import {PortfolioReview,parsePortfolioReview} from "./PortfolioReview";
afterEach(cleanup);
const row={id:"PORT-001",label:"Synthetic product",repository:"example/product",disposition:"clarify",recorded_priority:"C1",role:"Discovery",accountable_position:"POS-003",execution_overlay:"Named consumer only",investment_boundary:"No material build without review",dependency_boundary:"Unverified interface",continue_or_review_criteria:"Evidence of use",next_review_question:"Check customer demand",current_business_evidence:"unknown",financial_evidence:"unknown",review_outcome:"not_assessed",decision_ready:false};
const packet={schema:"arvectum.company.portfolio-review-packet/1",status:"review_candidate",derived:true,canonical_authority:false,organizational_authority_provided:false,coverage:"partial",review_completed:false,previous_review_at:null,portfolio_updated:"2026-10-06",prepared_at:"2026-11-20",source_commit:"a".repeat(40),owner_attention:"Reviewed boundary",cadence:{event:"material_event",monthly:"monthly_async_exception_scan",quarterly:"quarterly_integrated_revalidation",accountable_position:"POS-003",last_monthly_review:null,last_quarterly_review:null},source_refs:[{path:"fixture.md",blob:"b".repeat(40)}],rows:[row]};
const show=(v?:unknown)=>render(<LanguageProvider initialLanguage="ru"><PortfolioReview candidate={v}/></LanguageProvider>);
it("shows structure without fabricating company nodes when source is not admitted",()=>{
 show();expect(screen.getByText("Пакет управленческого пересмотра не допущен или недоступен.")).toBeTruthy();
 expect(screen.queryByText(/PORT-001/)).toBeNull();
});
it("separately presents recorded priority, overlay, investment, next review and uncertain evidence",()=>{
 show(packet);
 expect(screen.getByText("PORT-001 · Synthetic product")).toBeTruthy();
 expect(screen.getByText("clarify · C1")).toBeTruthy();
 expect(screen.getByText("Named consumer only")).toBeTruthy();
 expect(screen.getByText("No material build without review")).toBeTruthy();
 expect(screen.getByText("Check customer demand")).toBeTruthy();
 expect(screen.getByText("Не подтверждены")).toBeTruthy();
 expect(screen.getByText("Последние завершённые проверки не подтверждены.")).toBeTruthy();
 expect(screen.queryByRole("button")).toBeNull();
});
it("rejects fake authority, completed review, duplicates and financial certainty",()=>{
 for(const invalid of [{...packet,organizational_authority_provided:true},{...packet,review_completed:true},{...packet,rows:[row,row]},{...packet,rows:[{...row,financial_evidence:"verified"}]},{...packet,rows:[{...row,decision_ready:true}]},{...packet,cadence:{...packet.cadence,last_monthly_review:"2026-11-20"}},{...packet,source_commit:"z".repeat(40)}])
  expect(()=>parsePortfolioReview(invalid)).toThrow();
 show({...packet,review_completed:true});
 expect(screen.getByRole("status")).toBeTruthy();expect(screen.queryByText("PORT-001 · Synthetic product")).toBeNull();
});
