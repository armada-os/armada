export interface CompatTool {
  id: string;
  label: string;
}

const LEGACY_WINDOWS_COMPAT_TOOL = "proton-cachyos-11.0-arm64";

export function factoryDefaultTransition(
  explicitTool: string | undefined,
  stateLoaded: boolean,
  previousTool: string,
  nextTool: string,
): { oldTool: string; newTool: string } | null {
  if (explicitTool || !stateLoaded || !nextTool) return null;
  if (previousTool === nextTool) return null;
  return {
    oldTool: previousTool || LEGACY_WINDOWS_COMPAT_TOOL,
    newTool: nextTool,
  };
}

export function defaultWindowsCompatTool(
  tools: CompatTool[],
  defaults: string[],
): string {
  const available = new Set(tools.map((tool) => tool.id));
  return defaults.find((tool) => available.has(tool)) || "";
}
