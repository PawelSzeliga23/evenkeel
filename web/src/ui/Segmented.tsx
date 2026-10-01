import styles from "./ui.module.css";

export function Segmented<T extends string>({
  label, options, value, onChange, className,
}: {
  label: string; options: { value: T; label: string }[]; value: T | null; onChange: (value: T) => void;
  /** Extra class for a screen-specific layout of the segments. */
  className?: string;
}) {
  return (
    <div className={className ? `${styles.segmented} ${className}` : styles.segmented} role="group" aria-label={label}>
      {options.map((option) => (
        <button key={option.value} type="button" aria-pressed={option.value === value} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}
