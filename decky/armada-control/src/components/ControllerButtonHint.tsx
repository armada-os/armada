import { findModuleExport } from "@decky/ui";
import type { ComponentType } from "react";

interface ButtonGlyphProps {
  button: number;
  additionalClassName?: string;
}

// Decky does not export Steam's visible button glyph component.
const ButtonGlyph = findModuleExport((value) => typeof value === "function"
  && value.toString().includes("#ControllerButton_L1")
  && value.toString().includes("#ControllerButton_R1")) as ComponentType<ButtonGlyphProps> | undefined;
const buttons = findModuleExport((value) => Number.isFinite(value?.LeftBumper)
  && Number.isFinite(value?.RightBumper)) as { LeftBumper: number; RightBumper: number } | undefined;

export function ControllerButtonHint({ side }: { side: "left" | "right" }) {
  const button = side === "left" ? buttons?.LeftBumper : buttons?.RightBumper;
  return (
    <span className="armada-tab-bumper" aria-hidden="true">
      {ButtonGlyph && button !== undefined
        ? <ButtonGlyph button={button} additionalClassName="armada-tab-bumper-glyph" />
        : <span>{side === "left" ? "‹" : "›"}</span>}
    </span>
  );
}
