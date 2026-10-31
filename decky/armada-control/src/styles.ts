import { classMap, gamepadSliderClasses } from "@decky/ui";
import { theme } from "./theme";
import { visualStyles } from "./components/visualStyles";
import { tabNavigationStyles } from "./components/TabNavigation.styles";
import { disabledButtonStyles } from "./components/buttonStyles";

// Steam has several section styles, so one class module may not match the rendered section.
const sectionStyles = classMap
  .filter((classes) => classes.PanelSection && classes.PanelSectionTitle)
  .map((classes) => `
      .armada-control-tab-content .${classes.PanelSection} {
        margin-block-end: 0;
      }
      .armada-control-tab-content .${classes.PanelSection} ~ .${classes.PanelSection}:has(> .${classes.PanelSectionTitle}) {
        border-block-start: ${theme.separatorWidth} solid ${theme.separator};
        padding-block-start: ${theme.spaceLarge};
      }
      .armada-control-tab-content .${classes.PanelSectionTitle}:has(+ .armada-section-description, + * .armada-section-description) {
        padding-block-end: 0;
      }
  `).join("");

const descriptionStyles = classMap
  .filter((classes) => classes.FieldDescription)
  .map((classes) => `
      .armada-control-tabs .${classes.FieldDescription},
      .armada-control-dialog .${classes.FieldDescription} {
        color: ${theme.supportingText};
      }
      .armada-control-tabs .armada-note-error .${classes.FieldDescription},
      .armada-control-dialog .armada-note-error .${classes.FieldDescription} {
        color: ${theme.error};
      }
  `).join("");

const nativeSelector = (key: string) => {
  const names = [...new Set(classMap
    .filter((classes) => key !== "PanelSection" || classes.PanelSectionTitle)
    .map((classes) => classes[key]).filter(Boolean))];
  return names.length ? `:is(${names.map((name) => `.${name}`).join(", ")})` : ":not(*)";
};
const nativeField = nativeSelector("Field");
const nativeRow = nativeSelector("PanelSectionRow");
const nativeSection = nativeSelector("PanelSection");
const finalFieldStyles = `
      .armada-control-tab-content ${nativeSection} > ${nativeRow}:not(:has(~ :not(.armada-supporting-text))) ${nativeField}::after,
      .armada-control-tab-content ${nativeSection} > ${nativeField}:not(:has(~ :not(.armada-supporting-text)))::after,
      .armada-control-dialog .DialogControlsSection > ${nativeRow}:not(:has(~ :not(.armada-supporting-text))) ${nativeField}::after,
      .armada-control-dialog .DialogControlsSection > ${nativeField}:not(:has(~ :not(.armada-supporting-text)))::after {
        content: none;
      }
`;

export const styles = `
      ${disabledButtonStyles}
      .armada-loading-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: ${theme.spaceMedium};
        min-block-size: var(--armada-panel-available-height, 100%);
        min-inline-size: 0;
      }
      .armada-loading-spinner {
        inline-size: ${theme.loadingIndicatorSize};
        block-size: ${theme.loadingIndicatorSize};
        flex: none;
      }
      .armada-loading-state .armada-supporting-text {
        text-align: center;
      }
      .armada-control-tabs {
        box-sizing: border-box;
        margin-block-start: calc(0px - var(--armada-native-content-padding, 0px));
        width: 100%;
        max-width: 100%;
        min-width: 0;
        min-height: 0;
        display: flex;
        flex-direction: column;
      }
      ${tabNavigationStyles}
      .armada-tab-panels {
        min-width: 0;
        padding-block-start: ${theme.spaceLarge};
      }
      .armada-tab-panels:has(> .armada-control-tab-content > ${nativeSection}:first-child .armada-notice) {
        padding-block-start: 0;
      }
      ${sectionStyles}
      ${descriptionStyles}
      ${finalFieldStyles}
      .armada-control-tabs .armada-section-description.armada-supporting-text {
        padding-block-start: 0;
      }
      .armada-control-tabs .armada-control-tab-content {
        padding-block-end: ${theme.spaceMedium};
      }
      .armada-icon { display: block; width: 1.125em; height: 1.125em; flex: none; }
      .armada-truncated-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: start; }
      .armada-label-with-badge {
        display: flex;
        align-items: center;
        gap: ${theme.spaceMedium};
        inline-size: 100%;
        min-inline-size: 0;
      }
      .armada-label-with-badge-text {
        flex: 1;
        min-inline-size: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .armada-label-badge {
        flex: 0 1 auto;
        min-inline-size: 0;
        max-inline-size: 100%;
        padding: calc(${theme.spaceSmall} / 2) ${theme.spaceSmall};
        border: 1px solid currentColor;
        border-radius: ${theme.radius};
        font-size: ${theme.textCaption};
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .armada-control-tabs .armada-rgb-hue .${gamepadSliderClasses.SliderTrack} {
        --left-track-color: transparent;
        --colored-toggles-main-color: transparent;
        background: linear-gradient(90deg, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00);
      }
      .armada-control-tabs .armada-rgb-saturation .${gamepadSliderClasses.SliderTrack} {
        --left-track-color: transparent;
        --colored-toggles-main-color: transparent;
        background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 1));
        box-shadow: inset 0 0 0 1px ${theme.border};
      }
      :is(.armada-control-tabs, .armada-control-dialog) .armada-subheader {
        text-transform: uppercase;
        font-size: ${theme.textSubheading};
        font-weight: 600;
        letter-spacing: .03em;
        opacity: 0.7;
        margin: 0;
        padding: ${theme.spaceMedium} 0 ${theme.spaceSmall};
      }
      :is(.armada-control-tabs, .armada-control-dialog) .armada-note-error {
        color: ${theme.error};
        opacity: 1;
      }
      .afc-scope .afc-error {
        box-sizing: border-box;
        width: 100%;
        padding: ${theme.spaceMedium} ${theme.spaceLarge};
        font-size: ${theme.textSmall};
        line-height: 1.4;
        color: ${theme.error};
      }
      .afc-scope .afc-modal-error {
        box-sizing: border-box;
        width: 100%;
        padding: 0 0 ${theme.spaceMedium};
        font-size: ${theme.textSmall};
        line-height: 1.4;
        color: ${theme.error};
      }
      .armada-control-dialog-scroll {
        display: contents;
      }
      .armada-control-dialog-footer {
        box-sizing: border-box;
        width: 100%;
        min-width: 0;
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        gap: ${theme.spaceMedium};
      }
      .armada-control-dialog-footer > * {
        box-sizing: border-box;
        flex: 1 1 max-content;
        max-width: 100%;
        width: auto;
        margin: 0;
      }
      .afc-scope .afc-graph-focusable[aria-disabled="true"] {
        opacity: ${theme.disabledOpacity};
        cursor: not-allowed;
      }
      .afc-scope .afc-graph-focusable {
        display: block;
        width: 100%;
        box-sizing: border-box;
        border-radius: ${theme.radius};
        border: 2px solid transparent;
      }
      .afc-scope .afc-graph-focusable.afc-graph-focused {
        border-color: ${theme.accent};
        box-shadow: 0 0 0 2px ${theme.accent};
      }
      .afc-scope .afc-graph-focusable.afc-graph-editing.afc-graph-focused {
        border-color: ${theme.warning};
        box-shadow: 0 0 0 2px ${theme.warning};
      }
      .afc-scope .afc-points-drawer {
        margin: ${theme.spaceSmall} 0 ${theme.spaceSmall} ${theme.spaceLarge};
        padding: ${theme.spaceSmall} 0 ${theme.spaceSmall} ${theme.spaceMedium};
        background: ${theme.subtle};
        border-left: 2px solid ${theme.accent};
      }
      .afc-scope .afc-point-row {
        padding: 0 ${theme.spaceLarge};
      }
      .afc-scope .afc-point-row + .afc-point-row {
        margin-top: calc(-1 * ${theme.spaceMedium});
      }
      .afc-scope .afc-collapse {
        animation: armada-reveal ${theme.motion} ease;
      }
      @keyframes armada-reveal { from { opacity: 0; } to { opacity: 1; } }
      .afc-scope .afc-controller-hint {
        box-sizing: border-box;
        width: 100%;
        margin-top: ${theme.spaceSmall};
        padding: 0 0 ${theme.spaceSmall};
        font-size: ${theme.textCaption};
        line-height: 1.4;
        color: ${theme.warning};
      }
      ${visualStyles}
    `;
