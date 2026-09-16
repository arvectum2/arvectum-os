import { useWorkspaceLanguage } from "./i18n";

function navigateTo(href: string) {
  window.history.pushState({}, "", href);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function WorkspaceLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <a href={href} onClick={(event) => { event.preventDefault(); navigateTo(href); }}>{children}</a>;
}

export function Guide({ release }: { release: string }) {
  const { text } = useWorkspaceLanguage();

  return <section className="guide-page" aria-labelledby="guide-title">
    <header className="hero">
      <p className="eyebrow">{text("Arvectum OS · Руководство", "Arvectum OS · Guide")}</p>
      <h1 id="guide-title">{text("Что здесь можно делать", "What you can do here")}</h1>
      <p>{text(
        "Это руководство описывает возможности именно той версии Workspace, которая открыта сейчас.",
        "This guide describes the capabilities of the exact Workspace release currently open.",
      )}</p>
      <p><strong>{text("Версия Workspace", "Workspace release")}:</strong> <code>{release}</code></p>
    </header>

    <section aria-labelledby="guide-start-title">
      <h2 id="guide-start-title">{text("С чего начать", "Where to start")}</h2>
      <div className="home-actions" aria-label={text("Переходы из руководства", "Guide shortcuts")}>
        <WorkspaceLink href="/work">{text("Посмотреть задачи", "View tasks")}</WorkspaceLink>
        <WorkspaceLink href="/information">{text("Найти информацию", "Find information")}</WorkspaceLink>
        <WorkspaceLink href="/company-materials">{text("Материалы компании", "Company materials")}</WorkspaceLink>
        <WorkspaceLink href="/copilot">{text("Спросить Arvectum AI", "Ask Arvectum AI")}</WorkspaceLink>
      </div>
      <p>{text(
        "Если задач сейчас нет, это нормальное рабочее состояние: используйте поиск по доступному организационному контексту, задайте вопрос Arvectum AI или откройте нужный продуктовый контекст в разделе «Задачи».",
        "If there are no tasks now, that is a normal working state: search the available organizational context, ask Arvectum AI, or open the relevant product context under Tasks.",
      )}</p>
    </section>

    <section aria-labelledby="guide-capabilities-title">
      <h2 id="guide-capabilities-title">{text("Что работает сейчас", "What works now")}</h2>
      <dl>
        <div><dt>{text("Главная", "Home")}</dt><dd>{text("Показывает, что требует вашего внимания сейчас, и даёт короткие переходы к основным действиям.", "Shows what needs your attention now and provides shortcuts to primary actions.")}</dd></div>
        <div><dt>{text("Задачи", "Tasks")}</dt><dd>{text("Показывает только реальные текущие задачи владельца и доступные продуктовые контексты. Тестовые сценарии не выдаются за живую работу.", "Shows only real current owner tasks and available product contexts. Test scenarios are not presented as live work.")}</dd></div>
        <div><dt>{text("Документы", "Documents")}</dt><dd>{text("Ищет и открывает уже доступные Workspace записи, документы и знания с учётом текущих прав и организации.", "Searches and opens records, documents, and knowledge already available to Workspace under current access and organization scope.")}</dd></div>
        <div><dt>{text("Материалы компании", "Company materials")}</dt><dd>{text("Позволяет загружать поддерживаемые материалы ООО «Арвектум», отправлять точную staged-версию на review, принимать её через Governed Execution, находить текущие и заменённые версии и использовать принятые шаблоны и источники в разрешённых сценариях.", "Lets the owner upload supported Arvectum Company materials, submit an exact staged version for review, admit it through Governed Execution, find current and superseded versions, and reuse admitted templates and sources in permitted scenarios.")}</dd></div>
        <div><dt>Arvectum AI</dt><dd>{text("Отвечает на вопросы по доступному контексту и показывает источники. Принятый материал компании может участвовать в ответе только как точная текущая версия с явно разрешённым AI-reuse; в первой версии содержимое передаётся модели только для TXT/Markdown и только в минимизированных фрагментах по вопросу. Ответ остаётся временным и не является решением, разрешением, организационным полномочием или автоматически подтверждённым знанием.", "Answers questions over available context and shows sources. An admitted Company material can participate only as an exact current version with explicit AI reuse permission; in this first slice, raw content reaches the model only for TXT/Markdown and only as question-scoped minimized excerpts. The answer remains transient and is not a decision, permission, organizational authority, or automatically validated knowledge.")}</dd></div>
        <div><dt>{text("Настройки", "Settings")}</dt><dd>{text("Содержат сведения об организации, активность, технические проверки, тестовые сценарии и форму обратной связи для dogfooding.", "Contains organization information, activity, technical checks, test scenarios, and dogfooding feedback.")}</dd></div>
      </dl>
    </section>

    <section aria-labelledby="guide-limits-title">
      <h2 id="guide-limits-title">{text("Чего пока нет", "What is not available yet")}</h2>
      <p>{text(
        "Пока нет универсального RAG/индекса или автоматического извлечения текста из DOCX, PPTX, PDF и изображений для Arvectum AI. Такие форматы могут оставаться принятыми материалами и участвовать как проверяемые metadata-свидетельства, но их содержимое не OCR-ится и не интерпретируется этим AI-контуром.",
        "There is not yet a general RAG/index or automatic text extraction from DOCX, PPTX, PDF, and images for Arvectum AI. Those formats may remain admitted materials and participate as inspectable metadata evidence, but this AI path does not OCR or interpret their content.",
      )}</p>
      <p>{text(
        "Загрузка или принятие материала сами по себе не разрешают AI-use и не превращают файл в подтверждённое знание, стандарт, решение или источник полномочий. Для AI-grounding требуется отдельное явное разрешение повторного использования точной канонически принятой версии.",
        "Uploading or admitting a material does not by itself permit AI use or turn the file into validated knowledge, a standard, a decision, or an authority source. AI grounding requires a separate explicit reuse permission on the exact canonically admitted version.",
      )}</p>
    </section>

    <section aria-labelledby="guide-governance-title">
      <h2 id="guide-governance-title">{text("Как Workspace обращается с полномочиями", "How Workspace handles authority")}</h2>
      <p>{text(
        "Поиск, экран, кнопка или ответ ИИ сами по себе ничего не утверждают и не дают новых прав. Существенные изменения канонического состояния выполняются только через предусмотренный управляемый контур с повторной проверкой необходимых условий.",
        "Search results, a screen, a button, or an AI answer do not by themselves approve anything or grant new rights. Consequential canonical changes only occur through the governed path with the required checks revalidated.",
      )}</p>
    </section>
  </section>;
}
