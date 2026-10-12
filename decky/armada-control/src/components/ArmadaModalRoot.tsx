import { ModalRoot } from "@decky/ui";
import type { ModalRootProps } from "@decky/ui";
import { styles } from "../styles";

export function ArmadaModalRoot({ children, ...props }: ModalRootProps) {
  return (
    <ModalRoot {...props}>
      <style>{styles}</style>
      {children}
    </ModalRoot>
  );
}
