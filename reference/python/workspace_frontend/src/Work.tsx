import { ActionableWork } from "./ActionableWork";
import { MyWork } from "./MyWork";
import { Products } from "./Products";
import { useWorkspaceLanguage } from "./i18n";

export function Work() {
  const { text } = useWorkspaceLanguage();
  return <section className="work-page" aria-labelledby="work-title">
    <header className="hero">
      <p className="eyebrow">{text("Arvectum OS", "Arvectum OS")}</p>
      <h1 id="work-title">{text("Работа и задачи", "Work and tasks")}</h1>
      <p>{text("Текущие задачи, требующие внимания, и доступные продуктовые контексты.", "Current tasks requiring attention and available product contexts.")}</p>
    </header>
    <MyWork />
    <ActionableWork />
    <Products />
  </section>;
}
