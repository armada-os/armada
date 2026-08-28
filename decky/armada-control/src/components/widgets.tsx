import { Dropdown, Field, PanelSectionRow, SliderField, ToggleField } from "@decky/ui";
import type { ReactNode } from "react";
import type { DropdownChoice } from "../types";

type Option = string | DropdownChoice;

export function SelectEdit({ label, value, options, onChange, disabled, placeholder, wrapperClassName }: {
  label?: ReactNode;
  value: any;
  options: Option[];
  onChange: (data: any) => void;
  // Accepted but no longer honoured: the labelBelow branch used DropdownItemInternal,
  // which was dropped upstream to fix the Game Mode focus freeze (#272).
  labelBelow?: boolean;
  disabled?: boolean;
  placeholder?: string;
  wrapperClassName?: string;
}) {
  const rgOptions = options.map((option) => (typeof option === "string" ? { data: option, label: option } : option));
  const dropdown = label === undefined ? (
    <Dropdown disabled={disabled} strDefaultLabel={placeholder} selectedOption={value} rgOptions={rgOptions} onChange={(option) => onChange(option.data)} />
  ) : (
    <Field label={label} childrenLayout="below" childrenContainerWidth="max" disabled={disabled}>
      <Dropdown disabled={disabled} strDefaultLabel={placeholder} selectedOption={value} rgOptions={rgOptions} onChange={(option) => onChange(option.data)} />
    </Field>
  );
  return (
    <PanelSectionRow>
      {wrapperClassName ? <div className={wrapperClassName}>{dropdown}</div> : dropdown}
    </PanelSectionRow>
  );
}

export function ToggleRow({ label, value, onChange, disabled, description, wrapperClassName }: {
  label: ReactNode;
  value: any;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  description?: ReactNode;
  wrapperClassName?: string;
}) {
  const field = <ToggleField label={label} description={description} checked={!!value} disabled={disabled} onChange={onChange} />;
  return (
    <PanelSectionRow>
      {wrapperClassName ? <div className={wrapperClassName}>{field}</div> : field}
    </PanelSectionRow>
  );
}

export function SliderEdit({ label, value, min, max, step, onChange, format, disabled, showValue = true, wrapperClassName = "armada-slider-field" }: {
  label: ReactNode;
  value: any;
  min: number;
  max: number;
  step: number;
  onChange: (value: any) => void;
  format?: (value: number) => any;
  disabled?: boolean;
  showValue?: boolean;
  wrapperClassName?: string;
}) {
  const numeric = Number(value);
  return (
    <PanelSectionRow>
      <div className={wrapperClassName}>
        <SliderField
          label={label}
          value={Number.isFinite(numeric) ? numeric : min}
          min={min}
          max={max}
          step={step}
          showValue={showValue}
          disabled={disabled}
          onChange={(next) => onChange(format ? format(next) : next)}
        />
      </div>
    </PanelSectionRow>
  );
}
