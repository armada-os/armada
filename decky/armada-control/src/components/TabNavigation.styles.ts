import { theme } from "../theme";

export const tabNavigationStyles = `
  .armada-tab-navigation {
    --armada-tab-pill-radius: 2em;
    position: sticky;
    top: var(--armada-native-title-height, 0px);
    z-index: var(--armada-tab-header-layer, 1);
    background: ${theme.surface};
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr) auto auto;
    align-items: center;
    gap: calc(${theme.spaceSmall} / 4);
    flex: 0 0 auto;
    font-size: ${theme.tabText};
    padding-block-start: ${theme.spaceLarge};
    padding-block-end: ${theme.spaceMedium};
    padding-inline: ${theme.spaceLarge};
    border-bottom: ${theme.separatorWidth} solid ${theme.separator};
    overflow-x: clip;
    overflow-y: visible;
    animation-duration: ${theme.motion};
    animation-timing-function: ease-in-out;
  }
  .armada-control-tabs .armada-tab-navigation .armada-compact-button {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    min-width: 0;
    width: auto;
    max-width: 100%;
    margin: 0;
    padding: 0;
    font-size: inherit;
    overflow: visible;
  }
  .armada-control-tabs .armada-tab-navigation .armada-compact-button.armada-tab-selected,
  .armada-control-tabs .armada-tab-navigation .armada-compact-button.armada-tab-selected:is(:hover, :focus, :active, .gpfocus),
  .armada-control-tabs .armada-tab-navigation .armada-compact-button.armada-tab-neighbor,
  .armada-control-tabs .armada-tab-navigation .armada-compact-button.armada-tab-neighbor:is(:hover, :focus, :active, .gpfocus) {
    border-radius: var(--armada-tab-corners, var(--armada-tab-pill-radius));
  }
  .armada-tab-previous {
    --armada-tab-corners: 0 var(--armada-tab-pill-radius) var(--armada-tab-pill-radius) 0;
  }
  .armada-tab-next {
    --armada-tab-corners: var(--armada-tab-pill-radius) 0 0 var(--armada-tab-pill-radius);
  }
  .armada-tab-selected::before,
  .armada-tab-selected::after,
  .armada-tab-neighbor::before,
  .armada-tab-neighbor::after { border-radius: inherit; }
  .armada-control-tabs .armada-tab-navigation .armada-tab-neighbor:not(:hover):not(:focus):not(.gpfocus) {
    background: ${theme.subtle};
  }
  .armada-control-tabs .armada-tab-navigation .armada-tab-selected:not(:hover):not(:focus):not(.gpfocus) {
    background: ${theme.subtle};
    color: ${theme.text};
  }
  .armada-tab-bumper,
  .armada-tab-boundary {
    display: flex;
    align-items: center;
    justify-content: center;
    width: ${theme.tabHintSize};
    height: ${theme.tabHintSize};
    flex: none;
  }
  .armada-tab-bumper .armada-tab-bumper-glyph { display: block; width: 100%; height: 100%; }
  .armada-tab-current { position: relative; display: flex; align-items: center; justify-content: center; min-width: 0; }
  .armada-tab-title {
    box-sizing: border-box;
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: ${theme.spaceSmall};
    flex: 0 1 auto;
    width: fit-content;
    max-width: 100%;
    min-width: 0;
    font-size: ${theme.tabText};
    font-weight: 600;
    text-transform: none;
    text-align: center;
    line-height: 1.4;
    padding-block: ${theme.spaceSmall};
    padding-inline: ${theme.spaceMedium};
    color: inherit;
  }
  .armada-tab-icon { display: flex; flex: none; }
  .armada-tab-label { display: block; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .armada-tab-neighbor .armada-tab-title,
  .armada-tab-ghost .armada-tab-title { gap: 0; padding: ${theme.spaceSmall}; }
  .armada-tab-neighbor .armada-tab-label,
  .armada-tab-ghost .armada-tab-label { position: absolute; left: 100%; top: 50%; translate: 0 -50%; width: 0; opacity: 0; }
  .armada-tab-surface { position: absolute; inset: 0; border-radius: inherit; pointer-events: none; visibility: hidden; }
  .armada-tab-ghost { position: absolute; left: 0; top: 0; display: flex; pointer-events: none; visibility: hidden; border-radius: var(--armada-tab-pill-radius); }
  .armada-control-tabs .armada-tab-navigation[data-moving] .armada-compact-button { background: transparent; }
  .armada-tab-navigation[data-moving] .armada-tab-surface,
  .armada-tab-navigation[data-moving] .armada-tab-ghost { visibility: visible; }
  @media (prefers-reduced-motion: reduce) {
    .armada-tab-navigation { animation-duration: 0s; }
  }
`;
