export const styles = `
      .armada-control-tabs {
        height: 95%;
        width: 316px;
        position: fixed;
        margin-top: -12px;
        margin-left: -8px;
        overflow: hidden;
      }
      .armada-control-tabs > div > div:first-child::before {
        background: #0D141C;
        box-shadow: none;
        backdrop-filter: none;
      }
      .armada-control-tabs [role="tabpanel"] {
        padding-left: 0 !important;
        padding-right: 0 !important;
      }
      .armada-control-tabs .armada-control-tab-content {
        padding-bottom: 24px;
      }
      .armada-control-tabs .armada-slider-field {
        width: 100%;
        max-width: none;
        overflow: hidden;
      }
      .armada-control-tabs .armada-slider-field * {
        min-width: 0 !important;
        max-width: 100% !important;
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
        margin-left: 6px;
        padding-left: 6px;
      }
      .armada-control-tabs .armada-reset-row {
        padding: 0 14px 8px;
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
    `;
