import {cleanup,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {LanguageProvider} from "./i18n";
import {OperatingCadence} from "./OperatingCadence";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("shows event-first guide and integrated cadence, not confirmed history or actions",()=>{
 const fetch=vi.fn();vi.stubGlobal("fetch",fetch);
 render(<LanguageProvider initialLanguage="ru"><OperatingCadence/></LanguageProvider>);
 expect(screen.getByRole("heading",{name:"Операционный цикл"})).toBeTruthy();
 for(const x of ["По событию","Неделя","Месяц","Квартал"])expect(screen.getByText(x)).toBeTruthy();
 expect(screen.getByText(/Обязательной ежедневной проверки нет/)).toBeTruthy();
 expect(screen.getByText(/История завершённых контрольных обзоров не допущена/)).toBeTruthy();
 expect(screen.queryByRole("button")).toBeNull();
 expect(fetch).not.toHaveBeenCalled();
});
