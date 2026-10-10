import { gamepadDialogClasses, gamepadSliderClasses, gamepadTabbedPageClasses, quickAccessControlsClasses } from "@decky/ui";

export const styles = `
      .armada-control-tabs {
        height: var(--armada-menu-height, calc(100vh - 160px));
        width: 100%;
        max-width: 100%;
        min-width: 0;
        position: relative;
        margin-top: -12px;
        box-sizing: border-box;
      }
      .armada-control-tabs .${gamepadTabbedPageClasses.GamepadTabbedPage} {
        height: 100%;
        min-height: 0;
      }
      .armada-control-tabs > div > div:first-child::before {
        background: #0D141C;
        box-shadow: none;
        backdrop-filter: none;
      }
      .armada-control-tabs [role="tabpanel"],
      .armada-control-tabs .${gamepadTabbedPageClasses.TabContentsScroll} {
        padding-left: 0 !important;
        padding-right: 0 !important;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        box-sizing: border-box;
      }
      .armada-control-tabs .${gamepadTabbedPageClasses.TabContentsScroll} {
        scroll-padding-top: 64px;
        scroll-padding-bottom: 20px;
        padding-bottom: 16px;
      }
      .armada-control-tabs .${gamepadTabbedPageClasses.TabHeaderRowWrapper} {
        padding-left: 8px;
        padding-right: 8px;
      }
      .armada-control-tabs [role="tablist"] {
        display: flex;
        flex-wrap: nowrap;
        justify-content: center;
      }
      .armada-control-tabs [role="tab"] {
        flex: 0 1 auto;
        min-width: 0;
        box-sizing: border-box;
        padding-left: 6px !important;
        padding-right: 6px !important;
        display: flex !important;
        align-items: center;
        justify-content: center;
      }
      .armada-control-tabs [role="tab"] svg {
        display: block;
        margin: 0;
      }
      .armada-control-tabs .armada-control-tab-content {
        width: 100%;
        max-width: 100%;
        min-width: 0;
        box-sizing: border-box;
        padding-bottom: 24px;
      }
      .armada-control-tabs .armada-control-tab-content > * {
        min-width: 0;
        max-width: 100%;
        box-sizing: border-box;
      }
      .armada-control-tabs .armada-trackpads-tab {
        width: 100%;
        max-width: 100%;
        min-width: 0;
        box-sizing: border-box;
      }
      .armada-control-tabs .armada-trackpads-tab > * {
        max-width: 100% !important;
        min-width: 0 !important;
        box-sizing: border-box !important;
      }
      /* Steam's classic Fields normally bleed 16px beyond PanelSectionRow.
         A nested Tabs page is already bounded by Decky's content column. Give
         every tab one consistent inset, including fields without a row wrapper,
         instead of clipping expanded focus backgrounds and slider thumbs. */
      .armada-control-tabs .armada-control-tab-content .${quickAccessControlsClasses.PanelSection} {
        padding-left: 0;
        padding-right: 0;
        min-width: 0;
        box-sizing: border-box;
      }
      .armada-control-tabs .armada-control-tab-content .${quickAccessControlsClasses.PanelSectionTitle} {
        padding-left: 12px;
        padding-right: 12px;
      }
      .armada-control-tabs .armada-control-tab-content .${gamepadDialogClasses.Field} {
        --field-negative-horizontal-margin: 0px !important;
        margin-inline: 0 !important;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        box-sizing: border-box;
        padding-inline-start: calc(12px + var(--indent-level, 0) * 20px) !important;
        padding-inline-end: 12px !important;
        scroll-margin-top: 64px;
        scroll-margin-bottom: 20px;
      }
      .armada-control-tabs .armada-control-tab-content .${gamepadDialogClasses.FieldLabel},
      .armada-control-tabs .armada-control-tab-content .${gamepadDialogClasses.FieldDescription} {
        min-width: 0;
        overflow-wrap: anywhere;
      }
      .armada-control-tabs .armada-control-tab-content .${gamepadDialogClasses.FieldLabelValue} {
        flex-shrink: 0;
      }
      .armada-control-tabs .armada-control-tab-content .${gamepadDialogClasses.FieldChildrenInner} {
        min-width: 0;
        max-width: 100%;
      }
      .armada-control-tabs .armada-slider-field,
      .armada-control-tabs .armada-control-tab-content .afc-slider-field {
        width: 100%;
        min-width: 0;
        box-sizing: border-box;
        overflow: visible;
      }
      .armada-control-tabs .armada-control-tab-content button {
        min-width: 0;
        max-width: 100%;
        box-sizing: border-box;
      }
      .armada-control-tabs .armada-rgb-hue .${gamepadSliderClasses.SliderTrack} {
        --left-track-color: #0000;
        --colored-toggles-main-color: #0000;
        background: linear-gradient(90deg, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00);
      }
      .armada-control-tabs .armada-rgb-saturation .${gamepadSliderClasses.SliderTrack} {
        --left-track-color: #0000;
        --colored-toggles-main-color: #0000;
        background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 1));
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2);
      }
      .armada-control-tabs .armada-subheader {
        text-transform: uppercase;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.5px;
        opacity: 0.7;
        margin: 0;
        padding: 10px 12px 2px;
      }
      .armada-control-tabs .armada-field-note {
        box-sizing: border-box;
        width: 100%;
        margin-top: -12px;
        padding: 0 0 6px;
        font-size: 12px;
        line-height: 16px;
        opacity: 0.62;
      }
      .armada-control-tabs .armada-trackpads-note {
        box-sizing: border-box;
        width: 100%;
        max-width: 100%;
        padding: 3px 14px 9px;
        overflow-wrap: anywhere;
        font-size: 12px;
        line-height: 16px;
        opacity: 0.68;
      }
      .armada-control-tabs .armada-color-field {
        box-sizing: border-box;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }
      .armada-control-tabs .armada-color-field span {
        min-width: 0;
        overflow-wrap: anywhere;
      }
      .armada-control-tabs .armada-color-field input[type="color"] {
        flex: 0 0 52px;
        width: 52px;
        height: 34px;
        padding: 2px;
        border: 1px solid rgba(255,255,255,.25);
        border-radius: 6px;
        background: transparent;
      }
      .armada-control-tabs .armada-control-disabled {
        opacity: .4;
      }
      .armada-control-tabs .armada-note-error {
        color: #ff6b6b;
        opacity: 1;
      }
      .armada-control-tabs .armada-advanced-group {
        margin-left: 6px;
        padding-left: 6px;
      }
      .armada-control-tabs .armada-reset-row {
        padding: 0 0 8px;
      }
      .armada-control-tabs .armada-compat-note {
        box-sizing: border-box;
        width: 100%;
        padding: 8px 16px 8px;
        font-size: 12px;
        line-height: 16px;
        opacity: 0.62;
        text-align: left;
        justify-content: flex-start;
        align-self: stretch;
      }

      .afc-scope .afc-field-note {
        box-sizing: border-box;
        width: 100%;
        margin-top: 4px;
        padding: 0 0 6px;
        font-size: 12px;
        line-height: 16px;
        opacity: 0.62;
      }
      .afc-scope .afc-used-by-note {
        padding-bottom: 0;
      }
      .afc-scope .afc-note {
        box-sizing: border-box;
        width: 100%;
        margin-top: 6px;
        padding: 0 0 6px;
        font-size: 12px;
        line-height: 16px;
        opacity: 0.62;
      }
      .afc-scope .afc-reset-row {
        padding: 0 14px 8px;
      }
      .afc-scope .afc-control-inset {
        box-sizing: border-box;
        width: 100%;
        padding: 0 8px;
      }
      .afc-scope .afc-control-inset > * {
        min-width: 0;
        max-width: 100%;
      }
      .afc-scope .afc-control-inset button {
        width: 100% !important;
      }
      .afc-scope .afc-error {
        box-sizing: border-box;
        width: 100%;
        padding: 8px 16px;
        font-size: 12px;
        line-height: 16px;
        color: #ff6b6b;
      }
      /* Unscoped: DialogFooter is a sibling of DialogBody, not a descendant. */
      .afc-modal-footer {
        display: flex !important;
        flex-direction: column !important;
        gap: 8px;
      }
      .afc-modal-footer-row {
        display: flex;
        flex-direction: row;
        flex-wrap: nowrap;
        gap: 8px;
        width: 100%;
      }
      .afc-modal-footer-half {
        flex: 1;
        min-width: 0;
      }
      .afc-modal-footer-full {
        width: 100%;
      }
      .afc-scope .afc-modal-title {
        margin: 0;
        padding: 4px 0 10px;
        font-size: 20px;
        font-weight: 600;
      }
      .afc-scope .afc-modal-error {
        box-sizing: border-box;
        width: 100%;
        padding: 0 0 8px;
        font-size: 12px;
        line-height: 16px;
        color: #ff6b6b;
      }
      .afc-scope .afc-slider-field {
        width: 100%;
        max-width: none;
        overflow: hidden;
      }
      .afc-scope .afc-slider-field * {
        min-width: 0 !important;
        max-width: 100% !important;
      }
      .afc-scope .afc-graph-focusable {
        display: block;
        width: 100%;
        box-sizing: border-box;
        border-radius: 6px;
        border: 2px solid transparent;
      }
      .afc-scope .afc-graph-focusable.afc-graph-focused {
        border-color: #5cc8ff;
        box-shadow: 0 0 0 2px rgba(92, 200, 255, 0.35);
      }
      .afc-scope .afc-graph-focusable.afc-graph-editing.afc-graph-focused {
        border-color: #ffd166;
        box-shadow: 0 0 0 2px rgba(255, 209, 102, 0.45);
      }
      .afc-scope .afc-points-drawer {
        margin: 4px 0 4px 12px;
        padding: 6px 0 6px 10px;
        background: rgba(92, 200, 255, 0.06);
        border-left: 2px solid rgba(92, 200, 255, 0.45);
      }
      .afc-scope .afc-point-row {
        padding: 0 14px 0;
      }
      .afc-scope .afc-point-row + .afc-point-row {
        margin-top: -8px;
      }
      .afc-scope .afc-point-row-header {
        display: flex;
        align-items: stretch;
        gap: 6px;
      }
      .afc-scope .afc-point-row-header > *:first-child {
        flex: 1;
        min-width: 0;
      }
      .afc-scope .afc-point-row-header > *:last-child {
        flex: 0 0 40px;
        width: 40px;
      }
      .afc-scope .afc-point-row-header button {
        min-width: 0 !important;
        max-width: 100% !important;
      }
      .afc-scope .afc-point-row-header > *:last-child button {
        width: 100% !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
      }
      .afc-scope .afc-collapse {
        overflow: hidden;
        transition: max-height 200ms ease;
      }
      .afc-scope .afc-point-details-inner {
        margin: 4px 0 8px 8px;
        padding: 4px 4px 4px 6px;
      }
      .afc-scope .afc-controller-hint {
        box-sizing: border-box;
        width: 100%;
        margin-top: 4px;
        padding: 0 0 6px;
        font-size: 11px;
        line-height: 15px;
        color: #ffd166;
      }
      .afc-scope .afc-min-warning-button {
        border-left: 2px solid rgba(255, 209, 102, 0.6);
        background: rgba(255, 209, 102, 0.08);
        border-radius: 4px;
      }
      .afc-scope .afc-min-warning-hidden {
        display: none;
      }
      .afc-scope button:disabled,
      .afc-scope button[disabled] {
        opacity: 0.35 !important;
        filter: grayscale(70%) !important;
        cursor: not-allowed !important;
      }
    `;
