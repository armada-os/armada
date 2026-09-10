import type { CompatTool } from "./protonPolicy";

export function mapCompatTools(raw: any): CompatTool[] {
  const tools = Array.isArray(raw) ? raw : raw?.tools;
  if (!Array.isArray(tools)) return [];
  return tools
    .filter((tool: any) => !tool?.is_incompatible)
    .map((tool: any) => {
      const id = String(tool?.strToolName ?? tool?.strName ?? tool?.name ?? "");
      return {
        id,
        label: String(tool?.strDisplayName || tool?.display_name || id),
      };
    })
    .filter((tool: CompatTool) => tool.id);
}

// An empty tool list is valid on older clients and must not trigger fallback.
export async function readCompatTools(
  client: any,
  getCompatTools: (appid?: number) => Promise<unknown>,
  appid?: number,
): Promise<CompatTool[]> {
  if (appid === undefined && client?.Settings?.GetGlobalCompatTools) {
    return mapCompatTools(await client.Settings.GetGlobalCompatTools());
  }
  if (appid !== undefined && client?.Apps?.GetAvailableCompatTools) {
    return mapCompatTools(await client.Apps.GetAvailableCompatTools(appid));
  }
  return mapCompatTools(await getCompatTools(appid));
}
