import { Field, PanelSectionRow, TextField } from "@decky/ui";
import { useState } from "react";
import type { ReactNode } from "react";
import { SelectEdit, SliderEdit as BaseSliderEdit, ToggleRow } from "./widgets";
import { clamp } from "../lib/util";

export function PseudoDropdown({ label, value, options, onChange }: {
  label?: ReactNode;
  value: string;
  options: { data: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <SelectEdit label={label} value={value} options={options} onChange={onChange} wrapperClassName="afc-control-inset" />
  );
}

export function ToggleEdit({ label, description, checked, onChange }: {
  label: ReactNode;
  description?: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <ToggleRow label={label} value={checked} description={description} onChange={onChange} wrapperClassName="afc-control-inset" />
  );
}

export function NumberEdit({ label, value, rangeMin, rangeMax, onCommit }: {
  label: ReactNode;
  value: number;
  rangeMin: number;
  rangeMax: number;
  onCommit: (value: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? String(value);

  const commit = () => {
    if (draft === null) return;
    const parsed = parseInt(draft, 10);
    // Keeps an empty draft (e.g. mid on-screen-keyboard blur) instead of restoring the old value.
    if (!Number.isFinite(parsed)) return;
    onCommit(clamp(parsed, rangeMin, rangeMax));
    setDraft(null);
  };

  return (
    <PanelSectionRow>
      <div className="afc-control-inset">
        <Field label={label} childrenLayout="below" childrenContainerWidth="max">
          <TextField
            value={shown}
            onFocus={() => setDraft((current) => current ?? String(value))}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
          />
        </Field>
      </div>
    </PanelSectionRow>
  );
}

export function SliderEdit({ label, value, min, max, step, onChange, disabled }: {
  label: ReactNode;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <BaseSliderEdit
      label={label}
      value={value}
      min={min}
      max={max}
      step={step}
      onChange={onChange}
      disabled={disabled}
      wrapperClassName="afc-slider-field"
    />
  );
}
