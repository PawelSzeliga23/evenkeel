import { ListRow } from "../../ui/ListRow";
import ui from "../../ui/ui.module.css";

const CHOICES = [
  { to: "/dodaj/xtb", lead: "XTB", title: "Import z XTB", subtitle: "Pliki XLSX lub ZIP z historią rachunku" },
  { to: "/dodaj/obligacja", lead: "EDO", title: "Obligacja", subtitle: "Zakup obligacji skarbowych" },
  { to: "/dodaj/konto-oszczednosciowe", lead: "%", title: "Konto oszczędnościowe", subtitle: "Oprocentowanie, kapitalizacja i pierwsza wpłata" },
  { to: "/dodaj/operacja", lead: "zł", title: "Operacja gotówkowa", subtitle: "Wpłata, wypłata, odsetki lub opłata spoza XTB" },
];

export function AddScreen() {
  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Dodaj</h1>
      <div>
        {CHOICES.map((choice) => (
          <ListRow key={choice.to} to={choice.to} lead={choice.lead} title={choice.title} subtitle={choice.subtitle}
            value={<span aria-hidden="true" className="dim">›</span>} />
        ))}
      </div>
    </div>
  );
}
