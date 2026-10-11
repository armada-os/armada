import { gamepadSliderClasses, gamepadTabbedPageClasses } from "@decky/ui";

export const styles = `
      .armada-control-tabs {
        width: 100%;
        height: 95vh;
        min-width: 0;
        min-height: 0;
      }
      .armada-control-tabs > div {
        height: 100%;
        min-height: 0;
      }
      .armada-control-tabs > div > div:first-child::before {
        background: #0D141C;
        box-shadow: none;
        backdrop-filter: none;
      }
      .armada-control-tabs .${gamepadTabbedPageClasses.TabContents},
      .armada-control-tabs .${gamepadTabbedPageClasses.TabContentsScroll},
      .armada-control-tabs .armada-control-tab-content {
        min-width: 0;
      }
      .armada-control-tabs .${gamepadTabbedPageClasses.TabContentsScroll} {
        padding-left: 0;
        padding-right: 0;
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
        padding-left: 6px;
        padding-right: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .armada-control-tabs [role="tab"] svg {
        display: block;
        margin: 0;
      }
      .armada-control-tabs .armada-control-tab-content {
        padding-bottom: 24px;
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
        padding: 10px 0 2px;
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
      .armada-control-tabs .armada-note-error {
        color: #ff6b6b;
        opacity: 1;
      }
      .armada-control-tabs .armada-advanced-group {
        margin: 0 8px;
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
      .armada-control-panel-content,
      .afc-scope .armada-control-panel-content {
        padding: 0 8px;
      }
      .afc-scope .afc-error {
        box-sizing: border-box;
        width: 100%;
        padding: 8px 16px;
        font-size: 12px;
        line-height: 16px;
        color: #ff6b6b;
      }
      .afc-scope .afc-modal-error {
        box-sizing: border-box;
        width: 100%;
        padding: 0 0 8px;
        font-size: 12px;
        line-height: 16px;
        color: #ff6b6b;
      }
      .armada-control-dialog-footer {
        display: flex;
        flex-direction: row;
        gap: 8px;
      }
      .armada-control-dialog-footer > button {
        flex: 1 1 0;
        min-width: 0;
        width: auto;
        margin: 0;
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
        min-width: 0;
        max-width: 100%;
      }
      .afc-scope .afc-point-row-header > *:last-child button {
        width: 100%;
        padding-left: 0;
        padding-right: 0;
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
    `;
