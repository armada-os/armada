import { theme } from "../theme";

export const visualStyles = `
  .armada-calibration-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: ${theme.spaceMedium};
    align-items: start;
    margin-block-end: ${theme.spaceLarge};
  }
  .armada-calibration-control { min-width: 0; }
  .armada-calibration-label {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: ${theme.spaceMedium};
    margin-block-end: ${theme.spaceSmall};
    font: inherit;
    font-weight: 600;
  }
  .armada-calibration-surround {
    position: relative;
    box-sizing: border-box;
    width: min(100%, calc(${theme.stickSize} + 2 * ${theme.markerGutter}));
    padding: ${theme.markerGutter};
    margin-inline: auto;
  }
  .armada-calibration-plot { display: block; width: 100%; max-width: ${theme.stickSize}; margin: auto; }
  .armada-calibration-trigger { width: min(100%, ${theme.stickSize}); margin-inline: auto; }
  .armada-calibration-frame { fill: ${theme.subtle}; stroke: ${theme.border}; stroke-width: 1.5; }
  .armada-calibration-axis { stroke: ${theme.separator}; stroke-width: 1; }
  .armada-calibration-dot { fill: ${theme.accent}; stroke: ${theme.text}; stroke-width: 1.5; }
  .armada-calibration-marker { display: block; flex: none; width: ${theme.markerSize}; height: ${theme.markerSize}; }
  .armada-calibration-marker[data-side] { position: absolute; transform: translate(-50%, -50%); }
  .armada-calibration-marker[data-side="left"] { left: calc(${theme.markerGutter} / 2); top: 50%; }
  .armada-calibration-marker[data-side="right"] { left: calc(100% - ${theme.markerGutter} / 2); top: 50%; }
  .armada-calibration-marker[data-side="up"] { left: 50%; top: calc(${theme.markerGutter} / 2); }
  .armada-calibration-marker[data-side="down"] { left: 50%; top: calc(100% - ${theme.markerGutter} / 2); }
  .armada-calibration-marker-base { fill: ${theme.subtle}; stroke: ${theme.border}; }
  .armada-calibration-marker[data-complete="true"] .armada-calibration-marker-base { fill: ${theme.success}; stroke: ${theme.success}; }
  .armada-calibration-marker-progress { fill: none; stroke: ${theme.success}; }
  .armada-calibration-marker-progress[data-progressing="true"] { transition: stroke-dashoffset ${theme.motionFast} linear; }
  .armada-calibration-marker-check { fill: none; stroke: ${theme.text}; }
  .armada-calibration-instructions { text-align: center; }
  .armada-fan-graph { width: 100%; max-width: ${theme.graphWidth}; height: auto; margin-inline: auto; display: block; touch-action: none; user-select: none; }
  .armada-fan-graph text { font-size: ${theme.graphLabelSize}; fill: ${theme.muted}; }
  .armada-fan-graph-surface { fill: ${theme.subtle}; stroke: ${theme.separator}; }
  .armada-fan-graph-grid { stroke: ${theme.grid}; }
  .armada-fan-graph-stop { fill: ${theme.warning}; opacity: .14; }
  .armada-fan-graph-stop-line { stroke: ${theme.warning}; opacity: .55; }
  .armada-fan-graph .armada-fan-graph-warning { fill: ${theme.warning}; }
  .armada-fan-graph-curve { fill: none; stroke: ${theme.accent}; }
  .armada-fan-graph-marker-halo { fill: ${theme.text}; opacity: .18; }
  .armada-fan-graph-marker { fill: ${theme.text}; stroke: ${theme.surface}; }
  .armada-fan-graph .armada-fan-graph-temperature { fill: ${theme.text}; }
  .armada-fan-graph-hit-target { fill: transparent; cursor: grab; touch-action: none; }
  .armada-fan-graph-point { fill: ${theme.accent}; stroke: ${theme.surface}; }
  .armada-fan-graph-point[data-active="true"] { fill: ${theme.warning}; }
  @media (prefers-reduced-motion: reduce) {
    .armada-calibration-marker-progress[data-progressing="true"], .afc-scope .afc-collapse { transition: none; animation: none; }
  }
`;
