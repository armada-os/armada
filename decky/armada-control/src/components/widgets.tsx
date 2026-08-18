import { Dropdown, Field, PanelSection, PanelSectionRow, SliderField, ToggleField } from "@decky/ui";
import type { ReactNode } from "react";
import type { DropdownChoice } from "../types";

type Option = string | DropdownChoice;

export function SelectEdit({ label, value, options, onChange, labelBelow, disabled, placeholder }: {
  label?: ReactNode;
  value: any;
  options: Option[];
  onChange: (data: any) => void;
  labelBelow?: boolean;
  disabled?: boolean;
  placeholder?: string;
}) {
  const rgOptions = options.map((option) => (typeof option === "string" ? { data: option, label: option } : option));
  return (
    <PanelSectionRow>
      {label === undefined ? (
        <Dropdown disabled={disabled} strDefaultLabel={placeholder} selectedOption={value} rgOptions={rgOptions} onChange={(option) => onChange(option.data)} />
      ) : (
        <Field label={label} childrenLayout="below" childrenContainerWidth="max" disabled={disabled}>
          <Dropdown disabled={disabled} strDefaultLabel={placeholder} selectedOption={value} rgOptions={rgOptions} onChange={(option) => onChange(option.data)} />
        </Field>
      )}
    </PanelSectionRow>
  );
}

export function ToggleRow({ label, value, onChange, disabled, description }: {
  label: ReactNode;
  value: any;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  description?: ReactNode;
}) {
  return (
    <PanelSectionRow>
      <ToggleField label={label} description={description} checked={!!value} disabled={disabled} onChange={onChange} />
    </PanelSectionRow>
  );
}

export function SliderEdit({ label, value, min, max, step, onChange, format }: {
  label: ReactNode;
  value: any;
  min: number;
  max: number;
  step: number;
  onChange: (value: any) => void;
  format?: (value: number) => any;
}) {
  const numeric = Number(value);
  return (
    <PanelSectionRow>
      <div className="armada-slider-field">
        <SliderField
          label={label}
          value={Number.isFinite(numeric) ? numeric : min}
          min={min}
          max={max}
          step={step}
          showValue
          onChange={(next) => onChange(format ? format(next) : next)}
        />
      </div>
    </PanelSectionRow>
  );
}
