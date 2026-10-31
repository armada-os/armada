import { ButtonItem, DialogButton, DialogButtonPrimary, DropdownItem, Field, PanelSection, PanelSectionRow, SliderField, TextField, ToggleField, gamepadDialogClasses } from "@decky/ui";
import type { ReactNode } from "react";
import type { ButtonItemProps, DialogButtonProps, FieldProps, TextFieldProps } from "@decky/ui";
import type { DropdownChoice } from "../types";

type Option = string | DropdownChoice;
type Separator = "standard" | "thick" | "none";

export function ControlRow({ children }: { children: ReactNode }) {
  return <PanelSectionRow>{children}</PanelSectionRow>;
}

export function ReadOnlyRow({ label, description }: Pick<FieldProps, "label" | "description">) {
  return <ControlRow><Field label={label} description={description} focusable highlightOnFocus bottomSeparator="standard" /></ControlRow>;
}

export function SupportingText({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <Field className={["armada-supporting-text", className].filter(Boolean).join(" ")} description={children} bottomSeparator="none" focusable={false} highlightOnFocus={false} />;
}

export function SectionDescription({ children }: { children: ReactNode }) {
  return <SupportingText className="armada-section-description">{children}</SupportingText>;
}

export function Subsection({ title, children }: { title: ReactNode; children: ReactNode }) {
  return <><div className="armada-subheader" role="heading" aria-level={3}>{title}</div>{children}</>;
}

export function NoticeSection({ title, children }: { title: ReactNode; children: ReactNode }) {
  return <PanelSection><ControlRow>
    <Field className="armada-notice" label={title} description={children} bottomSeparator="none" focusable highlightOnFocus />
  </ControlRow></PanelSection>;
}

export function LabelWithBadge({ children, badge }: { children: ReactNode; badge: ReactNode }) {
  return <span className="armada-label-with-badge"><span className="armada-label-with-badge-text">{children}</span><span className="armada-label-badge">{badge}</span></span>;
}

export function ButtonRow({ children, variant = "secondary", bottomSeparator = "standard", ...props }: ButtonItemProps & { variant?: "primary" | "secondary" }) {
  if (variant === "primary") {
    const { layout, onClick, disabled, ...fieldProps } = props;
    return <ControlRow><Field {...fieldProps} childrenLayout={layout} childrenContainerWidth={props.childrenContainerWidth || "max"} bottomSeparator={bottomSeparator} disabled={disabled}>
      <DialogButtonPrimary disabled={disabled} onClick={onClick}>{children}</DialogButtonPrimary>
    </Field></ControlRow>;
  }
  return <ControlRow><ButtonItem {...props} bottomSeparator={bottomSeparator}>{children}</ButtonItem></ControlRow>;
}

export function CompactButton({ className = "", ...props }: DialogButtonProps) {
  return <DialogButton {...props} className={`${gamepadDialogClasses.NoMinWidth} armada-compact-button ${className}`} />;
}

export function SelectEdit({ label, description, value, options, onChange, disabled, placeholder, bottomSeparator = "standard" }: {
  label?: ReactNode;
  description?: ReactNode;
  value: any;
  options: Option[];
  onChange: (data: any) => void;
  disabled?: boolean;
  placeholder?: string;
  bottomSeparator?: Separator;
}) {
  const rgOptions = options.map((option) => (typeof option === "string" ? { data: option, label: option } : option));
  return <ControlRow>
    <DropdownItem
      label={label}
      description={description}
      bottomSeparator={bottomSeparator}
      layout="below"
      disabled={disabled}
      strDefaultLabel={placeholder}
      selectedOption={value}
      rgOptions={rgOptions}
      onChange={(option) => onChange(option.data)}
    />
  </ControlRow>;
}

export function TextEdit({ label, description, value, onChange, disabled, bottomSeparator = "standard", ...inputProps }: Omit<TextFieldProps, "label" | "description" | "onChange" | "value"> & {
  label: string;
  description?: ReactNode;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  bottomSeparator?: Separator;
}) {
  return <ControlRow>
    <Field label={label} description={description} childrenLayout="below" bottomSeparator={bottomSeparator} disabled={disabled}>
      <TextField {...inputProps} aria-label={label} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
    </Field>
  </ControlRow>;
}

export function ToggleRow({ label, value, onChange, disabled, description, bottomSeparator = "standard" }: {
  label: ReactNode;
  value: any;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  description?: ReactNode;
  bottomSeparator?: Separator;
}) {
  return <ControlRow>
    <ToggleField label={label} description={description} checked={!!value} disabled={disabled} onChange={onChange} bottomSeparator={bottomSeparator} />
  </ControlRow>;
}

export function SliderEdit({ label, description, value, min, max, step, onChange, format, disabled, showValue = true, wrapperClassName, bottomSeparator = "standard" }: {
  label: ReactNode;
  description?: ReactNode;
  value: any;
  min: number;
  max: number;
  step: number;
  onChange: (value: any) => void;
  format?: (value: number) => any;
  disabled?: boolean;
  showValue?: boolean;
  wrapperClassName?: string;
  bottomSeparator?: Separator;
}) {
  const numeric = Number(value);
  return <ControlRow>
    <SliderField
      className={wrapperClassName}
      bottomSeparator={bottomSeparator}
      label={label}
      description={description}
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
