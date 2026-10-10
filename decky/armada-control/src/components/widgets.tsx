import { ButtonItem, DropdownItem, PanelSectionRow, SliderField, ToggleField } from "@decky/ui";
import type { ReactNode } from "react";
import type { ButtonItemProps } from "@decky/ui";
import type { DropdownChoice } from "../types";

type Option = string | DropdownChoice;

export function ControlRow({ children }: { children: ReactNode }) {
  return <PanelSectionRow>{children}</PanelSectionRow>;
}

export function ButtonRow({ children, ...props }: ButtonItemProps) {
  return <ControlRow><ButtonItem {...props}>{children}</ButtonItem></ControlRow>;
}

export function SelectEdit({ label, value, options, onChange, disabled, placeholder }: {
  label?: ReactNode;
  value: any;
  options: Option[];
  onChange: (data: any) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const rgOptions = options.map((option) => (typeof option === "string" ? { data: option, label: option } : option));
  return <ControlRow>
    <DropdownItem
      label={label}
      layout="below"
      disabled={disabled}
      strDefaultLabel={placeholder}
      selectedOption={value}
      rgOptions={rgOptions}
      onChange={(option) => onChange(option.data)}
    />
  </ControlRow>;
}

export function ToggleRow({ label, value, onChange, disabled, description }: {
  label: ReactNode;
  value: any;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  description?: ReactNode;
}) {
  return <ControlRow>
    <ToggleField label={label} description={description} checked={!!value} disabled={disabled} onChange={onChange} />
  </ControlRow>;
}

export function SliderEdit({ label, value, min, max, step, onChange, format, disabled, showValue = true, wrapperClassName }: {
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
  return <ControlRow>
    <SliderField
      className={wrapperClassName}
      label={label}
      childrenContainerWidth="max"
      value={Number.isFinite(numeric) ? numeric : min}
      min={min}
      max={max}
      step={step}
      showValue={showValue}
      disabled={disabled}
      onChange={(next) => onChange(format ? format(next) : next)}
    />
  </ControlRow>;
}
