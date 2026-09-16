import type { DropdownChoice } from "../types";

// Mirrors the "Common Environment Variables" list published at
// https://armadaos.dev/compatibility/environment-variables/
export interface EnvPreset {
  name: string;
  description: string;
  // Closed list from the docs; absent means the value is free text.
  options?: DropdownChoice[];
  // A hint only. The docs show these inside examples and never state a default.
  example?: string;
  // The single value the docs give for this variable.
  value?: string;
}

export const envPresets: EnvPreset[] = [
  {
    name: "DXVK_FRAME_RATE",
    description: "Applies a frame limit to games using DXVK.",
    example: "60",
  },
  {
    name: "MESA_LOADER_DRIVER_OVERRIDE",
    description: "Overrides the driver loaded by Mesa. Most often used for better compatibility with OpenGL using the Zink driver, which translates OpenGL to Vulkan.",
    example: "zink",
  },
  {
    name: "MESA_VK_WSI_PRESENT_MODE",
    description: "Sets the Vulkan presentation mode, which is effectively V-sync mode.",
    options: [
      { data: "immediate", label: "immediate - Immediate, V-sync off" },
      { data: "mailbox", label: "mailbox - Mailbox, V-sync on" },
      { data: "relaxed", label: "relaxed - Relaxed FIFO, adaptive" },
      { data: "fifo", label: "fifo - FIFO, V-sync on" },
    ],
  },
  {
    name: "PROTON_USE_WINED3D",
    description: "Use the WineD3D library instead of DXVK for DirectX 9-11 games. Can help with compatibility issues.",
    value: "1",
  },
  {
    name: "PROTON_USE_WOW64",
    description: "Runs 32-bit binaries in 64-bit WOW64 mode. Can improve compatibility with older games and is sometimes required when using newer Proton builds with NTSYNC.",
    value: "1",
  },
  {
    name: "VKD3D_FEATURE_LEVEL",
    description: "Sets the DirectX feature level exposed to the game when using VKD3D. Lower values can improve compatibility.",
    options: [
      { data: "11_0", label: "11_0 - DirectX 11.0-level features" },
      { data: "11_1", label: "11_1 - DirectX 11.1-level features" },
      { data: "12_0", label: "12_0 - DirectX 12.0-level features" },
      { data: "12_1", label: "12_1 - DirectX 12.1-level features" },
      { data: "12_2", label: "12_2 - DirectX 12.2-level features" },
    ],
  },
  {
    name: "VKD3D_FRAME_RATE",
    description: "Applies a frame limit to games using VKD3D.",
    example: "60",
  },
  {
    name: "VKD3D_SHADER_MODEL",
    description: "Sets the highest shader model a game can use when using VKD3D. Lower values can improve compatibility.",
    options: [
      { data: "6_0", label: "6_0 - Shader Model 6.0" },
      { data: "6_1", label: "6_1 - Shader Model 6.1" },
      { data: "6_2", label: "6_2 - Shader Model 6.2" },
      { data: "6_3", label: "6_3 - Shader Model 6.3" },
      { data: "6_4", label: "6_4 - Shader Model 6.4" },
      { data: "6_5", label: "6_5 - Shader Model 6.5" },
      { data: "6_6", label: "6_6 - Shader Model 6.6" },
      { data: "6_7", label: "6_7 - Shader Model 6.7" },
      { data: "6_8", label: "6_8 - Shader Model 6.8" },
      { data: "6_9", label: "6_9 - Shader Model 6.9" },
    ],
  },
];

export const findPreset = (name: string): EnvPreset | undefined =>
  envPresets.find((preset) => preset.name === name);

// What a variable is currently set to, for prefilling the picker. A null in own
// is a tombstone that switches off an inherited variable, so it falls through to
// the global value rather than reading as "set to nothing".
export function resolveEnvValues(
  own: Record<string, string | null>,
  global: Record<string, string>,
): Record<string, string> {
  const values = { ...global };
  for (const [name, value] of Object.entries(own)) if (typeof value === "string") values[name] = value;
  return values;
}
