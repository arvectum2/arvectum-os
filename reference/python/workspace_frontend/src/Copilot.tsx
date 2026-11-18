import { useState } from "react";
import type { FormEvent } from "react";
import { askCopilot, WorkspaceApiError } from "./api";
import { useWorkspaceLanguage } from "./i18n";
import type { CopilotAnswer, CopilotClaimKind } from "./types";

const starters = {
  ru: ["Какие документы доступны для работы?", "Какие сведения подтверждены источниками?", "Каких данных не хватает для ответа?"],
  en: ["Which documents are available?", "Which facts are supported by sources?", "What information is missing?"],
};

export function Copilot({ csrfToken }: { csrfToken: string }) {
  const { language, text } = useWorkspaceLanguage();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<CopilotAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const claimLabels: Record<CopilotClaimKind, string> = {
    "source-context": text("Контекст источника", "Source context"), synthesis: text("Вывод ИИ", "AI synthesis"), uncertainty: text("Неопределённость", "Uncertainty"), "unavailable-evidence": text("Недоступные свидетельства", "Unavailable evidence"),
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault(); const normalized = question.trim(); if (!normalized || loading) return;
    setLoading(true); setError(null);
    try { setAnswer(await askCopilot(normalized, csrfToken)); }
    catch (caught) { setAnswer(null); setError(caught instanceof WorkspaceApiError ? caught.code : "COPILOT_UNAVAILABLE"); }
    finally { setLoading(false); }
  };

  return <section className="copilot" aria-labelledby="copilot-title">
    <div className="copilot-heading"><p className="eyebrow">Arvectum AI</p><h1 id="copilot-title">{text("Задайте вопрос Arvectum", "Ask Arvectum a question")}</h1><p>{text("Получите ответ с проверяемыми источниками по вашему рабочему контексту.", "Get an answer with inspectable sources about your work context.")}</p><p className="boundary-note">{text("Ответ опирается только на доступные источники. Проверяйте основания перед решением.", "Answers use only available sources. Check the evidence before making a decision.")}</p></div>
    <div className="copilot-starters" aria-label={text("Примеры вопросов", "Example grounded questions")}>{starters[language].map((starter) => <button key={starter} type="button" onClick={() => setQuestion(starter)}>{starter}</button>)}</div>
    <form className="copilot-form" onSubmit={(event) => void submit(event)}><label htmlFor="copilot-question">{text("Вопрос", "Question")}</label><textarea id="copilot-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={800} rows={5} placeholder={text("Спросите о записях, свидетельствах, продуктах, происхождении данных или текущем управляемом состоянии…", "Ask about organizational records, evidence, product context, provenance or current governed state…")} /><div className="copilot-form-footer"><small>{text("Для поиска используется только текущий серверно-авторизованный контекст рабочего пространства.", "Only the current server-authorized Workspace scope is eligible for retrieval.")}</small><button type="submit" disabled={!question.trim() || loading}>{loading ? text("Формируем ответ…", "Grounding answer…") : text("Спросить Arvectum", "Ask Arvectum")}</button></div></form>
    {error ? <div className="copilot-unavailable" role="alert"><strong>{text("Arvectum AI недоступен", "Copilot unavailable")}</strong><p>{text("Запрос нельзя безопасно обработать в текущем контексте.", "The request could not be answered safely in the current Workspace context.")}</p><code>{error}</code></div> : null}
    {answer ? <div className="copilot-answer" aria-live="polite">
      <div className="copilot-answer-heading"><div><p className="eyebrow">{text("Ответ с опорой на источники", "Grounded response")}</p><h2>{text("Ответ", "Answer")}</h2></div><span className="transient-badge">{text("Временный результат · не подтверждённое Знание", "Transient · not validated Knowledge")}</span></div>
      <div className="claim-list">{answer.claims.map((claim, index) => <article className={`claim-card claim-${claim.kind}`} key={`${claim.kind}-${index}`}><span className="claim-kind">{claimLabels[claim.kind]}</span><p>{claim.text}</p></article>)}</div>
      <section className="copilot-sources" aria-labelledby="copilot-sources-title"><h2 id="copilot-sources-title">{text("Проверяемые свидетельства", "Inspectable evidence")}</h2>{answer.sources.length ? <div className="source-list">{answer.sources.map((source) => <article className="source-card" key={source.id}><div className="source-card-topline"><span>{source.semantic_role}</span><span>{source.freshness}</span></div><h3>{source.label}</h3><p>{source.summary}</p><dl><div><dt>{text("Авторитет / источник", "Authority / source")}</dt><dd>{source.authority}</dd></div>{source.knowledge_role ? <div><dt>{text("Роль знания", "Knowledge role")}</dt><dd>{source.knowledge_role}</dd></div> : null}</dl><a href={source.open_href}>{text("Открыть свидетельство", "Open evidence in Workspace")}</a></article>)}</div> : <p className="boundary-note">{text("Недостаточно проверяемых свидетельств для обоснованного ответа.", "No inspectable evidence was sufficient to ground this question.")}</p>}</section>
      <div className="copilot-boundary-grid"><article><span className="eyebrow">{text("Модель", "Model")}</span><strong>{answer.model.used ? `${answer.model.provider} · ${answer.model.model}` : text("Синтез модели не использован", "No synthesis used")}</strong><p>{answer.model.failure ? `${text("Ограничение модели", "Model limitation")}: ${answer.model.failure}` : text("Свободный вывод модели может быть только синтезом, но не источником фактов или подтверждённым Знанием.", "Free-form model output can only appear as synthesis, never as source context or validated Knowledge.")}</p></article><article><span className="eyebrow">{text("Полномочия", "Authority")}</span><strong>{text("Не предоставлены", "Not provided")}</strong><p>{text("Вопрос не может выдать разрешение, организационные полномочия или значимое согласование.", "Asking a question cannot grant authorization, Organizational Authority or consequential approval.")}</p></article><article><span className="eyebrow">{text("Сохранение", "Persistence")}</span><strong>{text("Временный ответ", "Transient response")}</strong><p>{text("Вопрос и ответ не превращаются автоматически в Память, подтверждённое Знание или каноническое состояние.", "The question and answer are not silently promoted into Memory, validated Knowledge or canonical state.")}</p></article></div>
      <div className="copilot-follow-up"><div><strong>{text("Нужно выполнить значимое действие?", "Need a consequential follow-up?")}</strong><p>{text("Сначала откройте приведённые свидетельства или продуктовый контекст. Управляемое продолжение возможно только из контекста, реально связанного с соответствующим выполнением или решением.", "Inspect the cited evidence or product context first. A governed continuation may be offered only from context actually bound to the relevant execution or decision. Copilot does not choose an unrelated execution.")}</p></div>{answer.follow_up.href ? <a className="quiet-link" href={answer.follow_up.href}>{answer.follow_up.label}</a> : <span className="boundary-note">{text("Связанное продолжение недоступно.", "No context-bound continuation is available.")}</span>}</div>
    </div> : null}
  </section>;
}
