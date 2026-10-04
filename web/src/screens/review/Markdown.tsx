import { isValidElement, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "./Markdown.module.css";

/** The section a heading opens, by its words (emoji, numbering and case ignored), and its marker colour. */
const SECTION_COLOURS: [string, string][] = [
  ["W skrócie", "var(--amber)"], ["Ocena ogólna", "var(--amber)"], ["Mocne strony", "var(--gain)"], ["Ryzyka", "var(--loss)"],
  ["Rynek", "var(--series-2)"], ["Twoje instrumenty", "var(--series-2)"], ["Pomysły do rozważenia", "var(--series-4)"],
  ["Propozycje", "var(--amber)"], ["Pytania do przemyślenia", "var(--dim)"], ["Źródła", "var(--dim)"],
];

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children);
  return "";
}

function sectionOf(children: ReactNode): [string, string] | undefined {
  const words = textOf(children).toLowerCase().replace(/^[^\p{L}]+|[^\p{L}]+$/gu, "");
  return SECTION_COLOURS.find(([name]) => name.toLowerCase() === words);
}

const COMPONENTS: Components = {
  h2: ({ children }) => {
    const section = sectionOf(children);
    return (
      <h2 className={styles.section} data-section={section?.[0]}>
        <i className={styles.marker} style={{ background: section?.[1] ?? "var(--rule)" }} aria-hidden="true" />
        {children}
      </h2>
    );
  },
  a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
  // A remote image would load (and tell its server the review was opened) as soon as the review is shown: a link.
  img: ({ src, alt }) => (
    <a href={typeof src === "string" ? src : undefined} target="_blank" rel="noopener noreferrer">
      {alt ? `Obraz: ${alt}` : "Obraz"}
    </a>
  ),
  table: ({ children }) => <div className={styles.tableScroll} data-scroll="x"><table>{children}</table></div>,
};

/** Claude's answer as a README. Raw HTML is never rendered (no rehype-raw): it stays visible text. */
export function Markdown({ text }: { text: string }) {
  return (
    <article className={styles.markdown}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS} skipHtml={false}>{text}</ReactMarkdown>
    </article>
  );
}
