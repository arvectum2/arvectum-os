import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it} from "vitest";
import {LanguageProvider} from "./i18n";
import {OwnerPortfolioTrafficLight,buildTrafficRows,trafficAge} from "./OwnerPortfolioTrafficLight";
import type {OwnerQueue} from "./OwnerProjectQueue";
import fixture from "./__fixtures__/executive-preview.json";
afterEach(cleanup);
const base=fixture["company-owner-project-queue"] as unknown as OwnerQueue;
function sample():OwnerQueue{
 const projects=["Клиент","Публичная услуга","Продукт","Архив","Платформа"].map((label,i)=>({...base.projects[0],label,stage:i===1?"PUBLIC NO-GO":i===3?"Архив":"В работе"}));
 const names=["blocked","watch","blocked","hold","read_only_reconciliation"] as const;
 const items=projects.map((p,i)=>({...base.items[0],project:p.label,ref:"REF"+i,queue:names[i],action:"Проверить результат по источнику " + (i===0?"TZ-018":i)}));
 const sections=base.sections.map(s=>({...s,entries:s.key==="protect_now"?[{title:"Клиент — исполнение договора",next:"Передать результат и проверить приёмку",qualification:"Контроль уже открыт"}]:[]}));
 return {...base,projects,items,sections,counts:{...base.counts,projects:5,actions:5,queues:{prepare_within_existing_envelope:0,read_only_reconciliation:1,blocked:2,watch:1,hold:1}}};
}
it("prioritizes explicit protect-now, project-wide stops and paused records without inventing accepted green",()=>{
 const a=buildTrafficRows(sample());
 expect(a.map(x=>[x.label,x.color])).toEqual([["Клиент","critical"],["Публичная услуга","critical"],["Продукт","working"],["Платформа","working"],["Архив","paused"]]);
 expect(a[0].next).toBe("Передать результат и проверить приёмку");
 expect(a[2].hasBlocker).toBe(true);
 expect(a.some(x=>x.color==="verified")).toBe(false);
 expect(a[0].steps).toHaveLength(1);
 expect(a[0].steps[0].action).toContain("TZ-018");
});
it("treats snapshot timestamp as source age, not time of last button click",()=>{
 expect(trafficAge("2026-11-20",new Date("2026-11-21T23:00:00Z"))).toBe(1);
 expect(trafficAge("2026-11-20",new Date("2026-11-26T01:00:00Z"))).toBe(6);
 expect(trafficAge("2026-02-31",new Date("2026-11-21T00:00:00Z"))).toBeNull();
});
it("shows all projects, protects internal IDs, filters signals and expands original steps",()=>{
 render(<LanguageProvider initialLanguage="ru"><OwnerPortfolioTrafficLight data={sample()} state="ready" checked={new Date("2026-11-21T10:00:00Z")}/></LanguageProvider>);
 expect(screen.getByRole("table",{name:"Проекты и открытые действия"})).toBeTruthy();
 expect(screen.getAllByRole("rowgroup")).toHaveLength(5);
 expect(screen.getByText("Данные на 20 ноября 2026 г.")).toBeTruthy();
 expect(screen.getByText(/повторно читает утверждённый снимок/)).toBeTruthy();
 expect(screen.queryByText("TZ-018")).toBeNull();
 fireEvent.click(screen.getByRole("button",{name:/Требует внимания/}));
 expect(screen.getAllByRole("rowgroup")).toHaveLength(2);
 fireEvent.click(screen.getByRole("button",{name:/Подтверждено/}));
 expect(screen.queryAllByRole("rowgroup")).toHaveLength(0);
 expect(screen.getByText(/нет проектов данной категории/)).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:/Все проекты/}));
 fireEvent.click(screen.getAllByRole("button",{name:/Все шаги/})[0]);
 expect(screen.getByText(/Первоначальный статус:/)).toBeTruthy();
 expect(screen.getAllByRole("rowgroup")).toHaveLength(5);
});
it("fails closed when source is missing rather than displaying green zeros",()=>{
 render(<LanguageProvider initialLanguage="ru"><OwnerPortfolioTrafficLight data={null} state="unavailable" checked={null}/></LanguageProvider>);
 expect(screen.getByText(/Статусы неизвестны/)).toBeTruthy();
 expect(screen.queryByRole("table")).toBeNull();
});
