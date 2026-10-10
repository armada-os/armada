export const SIMPLIFIED_CHINESE_FONT_FAMILY =
  '"Motiva Sans", "Noto Sans CJK SC", "Source Han Sans SC", Arial, Helvetica, sans-serif';

export const styles = `
      .armada-store-zh-cn, .armada-store-zh-cn * { font-family: ${SIMPLIFIED_CHINESE_FONT_FAMILY}; }
      .armada-store-search { position: relative; }
      .armada-store-search > span {
        position: absolute;
        top: 50%;
        left: 12px;
        transform: translateY(-50%);
        pointer-events: none;
        opacity: 0.65;
        z-index: 1;
      }
      .armada-store-search input { padding-left: 40px !important; }
      .armada-store-row {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        min-height: 32px;
      }
      .armada-store-row svg {
        flex: none;
        opacity: 0.9;
      }
      .armada-store-row img,
      .armada-store-icon-fallback {
        width: 28px;
        height: 28px;
        border-radius: 6px;
        flex: none;
      }
      .armada-store-icon-fallback {
        background: #2a475e;
        color: #c7d5e0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 14px;
      }
      .armada-store-row-text {
        flex: 1;
        min-width: 0;
        text-align: left;
      }
      .armada-store-row-name {
        font-size: 16px;
        line-height: 22px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .armada-store-row-state {
        flex: none;
        display: flex;
        align-items: center;
        font-size: 13px;
        opacity: 0.75;
      }
      .armada-store-row-state.armada-store-error {
        color: #ff7a7a;
        opacity: 1;
      }
      .armada-store-row-state.armada-store-update {
        color: #1a9fff;
        opacity: 1;
      }
      .armada-store-progress {
        height: 3px;
        border-radius: 2px;
        background: rgba(255, 255, 255, 0.15);
        overflow: hidden;
        margin-top: 3px;
      }
      .armada-store-progress > div {
        height: 100%;
        background: #1a9fff;
        transition: width 0.4s;
      }
    `;
