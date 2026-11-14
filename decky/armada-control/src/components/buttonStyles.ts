import { theme } from "../theme";

const buttonScope = [
  ".armada-control-tabs .armada-control-tab-content",
  ".armada-control-tabs .armada-tab-navigation",
  ".armada-control-dialog-position .armada-control-dialog",
].join(", ");
const disabledButton = `:is(${buttonScope}) button.DialogButton:is(.Disabled, :disabled)`;

export const disabledButtonStyles = `
  ${disabledButton} {
    background: ${theme.disabledSurface};
    color: ${theme.disabledText};
    opacity: 1;
    cursor: not-allowed;
    outline: none;
    box-shadow: none;
  }
  ${disabledButton}:is(.gpfocus, :focus-visible, :hover) {
    background: ${theme.disabledSelectedSurface};
    color: ${theme.disabledText};
    outline: none;
    box-shadow: none;
  }
`;
