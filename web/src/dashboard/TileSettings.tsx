/** Plan 9: a tile's settings, in its place on the Pulpit while editing. */
import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { useAccountSelection } from "../accounts/AccountSelection";
import { api } from "../api/endpoints";
import { keys } from "../api/queryKeys";
import type { AnalyticsPeriod } from "../api/types";
import styles from "./Dashboard.module.css";
import {
  ANALYSIS_PERIODS, KINDS, PRICE_RANGES, VALUE_RANGES, type AllocationBy, type PriceRange, type Tile, type TileSize,
  type ValueRange,
} from "./layout";
import { METRIC_OPTIONS, type MetricKey } from "./metrics";

const VALUE_RANGE_NAMES: Record<ValueRange, string> = { "1M": "1 miesiąc", "3M": "3 miesiące", "1R": "1 rok", ALL: "Wszystko" };
const PRICE_RANGE_NAMES: Record<PriceRange, string> = {
  buy: "Od zakupu", "6m": "6 miesięcy", "1y": "1 rok", "5y": "5 lat", max: "Maksymalny",
};
const PERIOD_NAMES: Record<AnalyticsPeriod, string> = {
  "1m": "1 miesiąc", "3m": "3 miesiące", "1y": "1 rok", ytd: "Od początku roku", all: "Cały okres",
};
const BY_NAMES: Record<AllocationBy, string> = { kind: "Typ", account: "Konto", currency: "Waluta" };
const SIZE_NAMES: Record<TileSize, string> = { S: "mały", M: "średni", L: "duży" };

function Select<T extends string | number>({ label, value, options, onChange }: {
  label: string; value: T; options: readonly { value: T; label: string }[]; onChange: (value: T) => void;
}) {
  const id = useId();
  return (
    <label className={styles.tileField} htmlFor={id}>
      <span>{label}</span>
      <select id={id} value={String(value)} onChange={(e) => {
        const chosen = options.find((o) => String(o.value) === e.target.value);
        if (chosen) onChange(chosen.value);
      }}>
        {options.map((o) => <option key={String(o.value)} value={String(o.value)}>{o.label}</option>)}
      </select>
    </label>
  );
}

const entries = <K extends string>(names: Record<K, string>, keys: readonly K[]) => keys.map((value) => ({ value, label: names[value] }));

function PriceChartFields({ tile, onSettings }: { tile: Tile<"price_chart">; onSettings: (s: Tile<"price_chart">["settings"]) => void }) {
  const [accountIds, , ready] = useAccountSelection();
  const positions = useQuery({ queryKey: keys.positions(accountIds), queryFn: () => api.positions(accountIds), enabled: ready });
  const holdings = (positions.data ?? []).filter((p) => p.kind === "instrument" && p.instrument_id !== null);
  const { account_id: accountId, instrument_id: instrumentId, range } = tile.settings;
  const chosen = accountId !== null && instrumentId !== null ? `${accountId}:${instrumentId}` : "";
  const options = [
    ...(chosen === "" ? [{ value: "", label: "Wybierz walor" }] : []),
    ...holdings.map((p) => ({ value: `${p.account_id}:${p.instrument_id}`, label: `${p.name} · ${p.account_name}` })),
  ];
  if (chosen !== "" && !options.some((o) => o.value === chosen)) options.unshift({ value: chosen, label: "Walor spoza portfela" });
  return (
    <>
      <Select label="Walor" value={chosen} options={options} onChange={(value) => {
        const [a, i] = value.split(":").map(Number);
        onSettings({ ...tile.settings, account_id: a ?? null, instrument_id: i ?? null });
      }} />
      <Select label="Zakres" value={range} options={entries(PRICE_RANGE_NAMES, PRICE_RANGES)}
        onChange={(next) => onSettings({ ...tile.settings, range: next })} />
    </>
  );
}

function MetricChoice({ chosen, max, onChange }: { chosen: MetricKey[]; max: number; onChange: (next: MetricKey[]) => void }) {
  return (
    <fieldset className={styles.tileChoices}>
      <legend>{`Miary (od 1 do ${max})`}</legend>
      {METRIC_OPTIONS.map((option) => {
        const on = chosen.includes(option.value);
        return (
          <label key={option.value}>
            <input type="checkbox" checked={on} disabled={on ? chosen.length === 1 : chosen.length >= max}
              onChange={() => onChange(on ? chosen.filter((m) => m !== option.value)
                : METRIC_OPTIONS.map((o) => o.value).filter((m) => m === option.value || chosen.includes(m)))} />
            {option.label}
          </label>
        );
      })}
    </fieldset>
  );
}

function KindFields({ tile, onSettings }: { tile: Tile; onSettings: (settings: Tile["settings"]) => void }) {
  switch (tile.kind) {
    case "summary":
      return (
        <>
          {tile.settings.fields.map((field, index) => (
            <Select key={index} label={`Pole ${index + 1}`} value={field} options={METRIC_OPTIONS}
              onChange={(next) => onSettings({ fields: tile.settings.fields.map((f, i) => (i === index ? next : f)) })} />
          ))}
        </>
      );
    case "metric":
      return <Select label="Miara" value={tile.settings.metric} options={METRIC_OPTIONS} onChange={(metric) => onSettings({ metric })} />;
    case "value_chart":
      return <Select label="Zakres" value={tile.settings.range} options={entries(VALUE_RANGE_NAMES, VALUE_RANGES)}
        onChange={(range) => onSettings({ range })} />;
    case "price_chart":
      return <PriceChartFields tile={tile} onSettings={onSettings} />;
    case "allocation":
      return <Select label="Według" value={tile.settings.by} options={entries(BY_NAMES, ["kind", "account", "currency"] as const)}
        onChange={(by) => onSettings({ by })} />;
    case "analysis":
      return (
        <>
          <Select label="Okres" value={tile.settings.period} options={entries(PERIOD_NAMES, ANALYSIS_PERIODS)}
            onChange={(period) => onSettings({ ...tile.settings, period })} />
          <MetricChoice chosen={tile.settings.metrics} max={6} onChange={(metrics) => onSettings({ ...tile.settings, metrics })} />
        </>
      );
    case "movers":
      return <Select label="Ile pozycji" value={tile.settings.count}
        options={[3, 5, 10].map((n) => ({ value: n as 3 | 5 | 10, label: String(n) }))} onChange={(count) => onSettings({ count })} />;
    default:
      return <p className="dim">Ten kafelek nie ma ustawień.</p>;
  }
}

export function TileSettings({ tile, isFirst, isLast, onChange, onMove, onClose }: {
  tile: Tile; isFirst: boolean; isLast: boolean;
  onChange: (patch: { size?: TileSize; settings?: Tile["settings"] }) => void;
  onMove: (step: -1 | 1) => void; onClose: () => void;
}) {
  const sizes = KINDS[tile.kind].sizes;
  const sizeName = useId();
  return (
    <div className={styles.tileSettings}>
      <b>{KINDS[tile.kind].name}</b>
      {sizes.length > 1 && (
        <fieldset className={styles.tileChoices} data-inline>
          <legend>Rozmiar (na komputerze)</legend>
          {sizes.map((size) => (
            <label key={size} title={SIZE_NAMES[size]}>
              <input type="radio" name={sizeName} value={size} checked={tile.size === size}
                onChange={() => onChange({ size })} />
              {size}
            </label>
          ))}
        </fieldset>
      )}
      <KindFields tile={tile} onSettings={(settings) => onChange({ settings })} />
      <div className={styles.tileActions}>
        <button type="button" className={styles.tileRetry} disabled={isFirst} onClick={() => onMove(-1)}>Przesuń wcześniej</button>
        <button type="button" className={styles.tileRetry} disabled={isLast} onClick={() => onMove(1)}>Przesuń później</button>
        <button type="button" className={styles.tileRetry} onClick={onClose} aria-label="Zamknij ustawienia">Gotowe</button>
      </div>
    </div>
  );
}
