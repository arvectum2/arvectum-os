import { useCallback, useEffect, useState } from "react";
import { loadCompanySourceWatch } from "./f11Api";
import type { CompanySourceWatchCandidate } from "./f11Types";
import { useWorkspaceLanguage } from "./i18n";

type State = {kind:"loading"}|{kind:"unavailable"}|{kind:"ready"; value:CompanySourceWatchCandidate};

const signals:Record<string,[string,string]> = {
  changed_source_review_required:["Изменился отслеживаемый файл — нужна проверка","Tracked file changed — review needed"],
  incomplete_source_evidence:["Не хватает подтверждений источника","Source evidence incomplete"],
  unscoped_repo_activity_review:["Активность репозитория вне отслеживаемого файла","Other repository activity"],
  existing_os_collector_review_required:["Точное чтение делегировано WSF-07A","Exact read delegated to WSF-07A"],
  observed_source_unchanged:["Отслеживаемый файл не менялся","Tracked file unchanged"],
};

export function CompanySourceWatch(){
  const {language,text}=useWorkspaceLanguage();
  const [state,setState]=useState<State>({kind:"loading"});
  const [seq,setSeq]=useState(0);
  const refresh=useCallback(()=>setSeq(x=>x+1),[]);
  useEffect(()=>{
    let active=true;
    setState({kind:"loading"});
    void loadCompanySourceWatch().then(value=>{
      if(!active)return;
      const admitted=value?.schema==="arvectum.company.source-watch-view/1" &&
        value.derived===true && value.canonical_authority===false &&
        value.business_status_updated===false && value.organizational_authority_provided===false &&
        value.coverage?.projects===22 && value.coverage?.source_refs===35 &&
        value.coverage?.os_exact_paths_delegated===5 &&
        value.coverage?.review_signals && Array.isArray(value.projects) && value.projects.length===22 &&
        (value.state==="current-observation"||value.state==="stale");
      setState(admitted?{kind:"ready",value}:{kind:"unavailable"});
    }).catch(()=>{if(active)setState({kind:"unavailable"});});
    return()=>{active=false;};
  },[seq]);
  const view=state.kind==="ready"?state.value:null;
  const counts=view?.coverage.review_signals ?? {};
  const changed=counts.changed_source_review_required??0;
  const indirect=counts.unscoped_repo_activity_review??0;
  const incomplete=(counts.incomplete_source_evidence??0)+(counts.existing_os_collector_review_required??0);
  const label=(key:string)=>text(...(signals[key]??["Неизвестный сигнал — требуется сверка","Unknown signal — review required"]));
  return <section className="company-card" aria-label={text("Наблюдение за дорожными картами","Roadmap source observations")}>
    <header className="company-card-head">
      <div><h2>{text("Изменения дорожных карт · Company Source Watch","Roadmap changes · Company Source Watch")}</h2>
        <p>{text("Наблюдения по источникам — не утверждение завершения или смена бизнес-статуса.","Source observations are not completion acceptance or business status updates.")}</p></div>
      <button type="button" onClick={refresh} disabled={state.kind==="loading"}>{text("Перечитать отчёт","Re-read report")}</button>
    </header>
    {state.kind==="loading"&&<p role="status">{text("Читаем сохранённый отчёт…","Reading saved report…")}</p>}
    {state.kind==="unavailable"&&<p role="status">{text("Отчёт Company не допущен или недоступен. Сведения не подтверждены.","Company report unavailable or not admitted. Evidence unverified.")}</p>}
    {view&&<>
      {view.state==="stale"&&<p role="alert">{text("Отчёт устарел; данные нельзя считать текущими.","Report is stale; observations are not current.")}</p>}
      <p>{text("Проверено: ","Observed: ")}{new Date(view.scanned_at).toLocaleString(language==="ru"?"ru-RU":"en-GB")} · {text("Снимок бизнес-очереди от","Business queue baseline dated")} {view.source_as_of}</p>
      <div className="project-portfolio-summary"><span>{view.coverage.projects} {text("проектов","projects")}</span><span>{view.coverage.source_refs} {text("ссылок на источники","source references")}</span><span>{changed} {text("изменений файлов на проверку","file changes to review")}</span><span>{indirect} {text("другой активности репозиториев","other repository activity")}</span><span>{incomplete} {text("недостаточно данных / делегировано","incomplete / delegated")}</span></div>
      <details><summary>{text("Сигналы по всем проектам","Review all project signals")} · {view.projects.length}</summary>
        <ul>{view.projects.map(p=><li key={p.project}><strong>{p.project}</strong> — {label(p.review_signal)}</li>)}</ul>
      </details>
      <p className="hub-boundary">{text("Пять точных файлов отслеживает WSF-07A отдельно. Этот отчёт не подтверждает здоровье сборщика, решение собственника или статус DONE.","Five exact source files are delegated to WSF-07A. This report does not attest collector health, owner approval or DONE status.")}</p>
    </>}
  </section>;
}
