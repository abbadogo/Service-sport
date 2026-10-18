import { validateSetting } from "../lib/settings";
import type { SettingSpec } from "../types";

interface Props {
  specs: SettingSpec[];
  values: Record<string, string>;
  onChange: (key: string, text: string) => void;
  onReset: () => void;
}

export function SettingsPanel({ specs, values, onChange, onReset }: Props) {
  const groups = [...new Set(specs.map((s) => s.group))];
  return (
    <section className="card" aria-label="Game settings">
      <div className="row">
        <h2>Settings</h2>
        <button type="button" onClick={onReset}>Reset to defaults</button>
      </div>
      {groups.map((g) => (
        <fieldset key={g}>
          <legend>{g}</legend>
          {specs.filter((s) => s.group === g).map((s) => {
            const text = values[s.key] ?? String(s.default);
            const error = validateSetting(s, text);
            const isToggle = s.minimum === 0 && s.maximum === 1 && s.step === 1; // on/off rule
            return (
              <div className="field" key={s.key}>
                <label htmlFor={`set-${s.key}`}>{s.label}</label>
                {isToggle ? (
                  <input
                    id={`set-${s.key}`}
                    type="checkbox"
                    checked={text === "1"}
                    aria-describedby={`desc-${s.key}`}
                    onChange={(e) => onChange(s.key, e.target.checked ? "1" : "0")}
                  />
                ) : (
                  <input
                    id={`set-${s.key}`}
                    type="number"
                    inputMode="decimal"
                    step={s.step}
                    min={s.minimum}
                    max={s.maximum}
                    value={text}
                    aria-invalid={error !== null}
                    aria-describedby={`desc-${s.key}`}
                    onChange={(e) => onChange(s.key, e.target.value)}
                  />
                )}
                <small id={`desc-${s.key}`} className="muted">{s.description}</small>
                {error && <small role="alert" className="error">{error}</small>}
              </div>
            );
          })}
        </fieldset>
      ))}
    </section>
  );
}
