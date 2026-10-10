import { ButtonItem, DialogBody, DialogButton, DialogFooter, ModalRoot } from "@decky/ui";
import { useState } from "react";
import { trackpadText as t } from "../lib/trackpadText";
import type { TrackpadShortcutButton } from "../types";
import { SelectEdit } from "./widgets";

const BUTTONS: TrackpadShortcutButton[] = [
  "Steam", "Select", "Start", "L3", "R3", "L1", "R1", "L2", "R2", "A", "B", "X", "Y",
];

export function TrackpadShortcutModal({ initial, onSave, closeModal }: {
  initial: TrackpadShortcutButton[];
  onSave: (buttons: TrackpadShortcutButton[]) => void;
  closeModal?: () => void;
}) {
  const [buttons, setButtons] = useState<TrackpadShortcutButton[]>([...initial]);
  const addButton = () => {
    const next = BUTTONS.find((button) => !buttons.includes(button));
    if (next && buttons.length < 4) setButtons([...buttons, next]);
  };
  return (
    <ModalRoot onCancel={() => closeModal?.()}>
      <DialogBody>
        <h2>{t("trackpads.shortcutEdit")}</h2>
        <p>{t("trackpads.shortcutChoose")}</p>
        {buttons.map((button, index) => (
          <SelectEdit
            key={index}
            label={`${t("trackpads.shortcutButton")} ${index + 1}`}
            value={button}
            options={BUTTONS.filter((option) => option === button || !buttons.includes(option))}
            onChange={(next: TrackpadShortcutButton) => setButtons((current) =>
              current.map((value, position) => position === index ? next : value))}
          />
        ))}
        <ButtonItem layout="below" onClick={addButton} disabled={buttons.length >= 4}>
          {t("trackpads.shortcutAdd")}
        </ButtonItem>
        <ButtonItem layout="below" onClick={() => setButtons(buttons.slice(0, -1))} disabled={buttons.length <= 1}>
          {t("trackpads.shortcutRemove")}
        </ButtonItem>
      </DialogBody>
      <DialogFooter>
        <DialogButton onClick={() => closeModal?.()}>{t("trackpads.cancel")}</DialogButton>
        <DialogButton onClick={() => { onSave(buttons); closeModal?.(); }}>
          {t("trackpads.save")}
        </DialogButton>
      </DialogFooter>
    </ModalRoot>
  );
}
