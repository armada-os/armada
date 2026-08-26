export type Locale = "en" | "zh-CN";

const zhCN = {
  "Loading": "正在加载",
  "Default": "默认",
  "Native": "原生",
  "Custom": "自定义",
  "Use Default": "使用默认值",
  "Follow Steam": "跟随 Steam",
  "All Cores": "全部核心",
  "Big Cores": "大核心",
  "Prime Cores": "超大核心",
  "Little Cores": "小核心",
  "None": "无",
  "Small": "轻度",
  "Medium": "中度",
  "Large": "重度",
  "Eco": "节能",
  "Balanced": "均衡",
  "Performance": "性能",
  "Ondemand": "按需",
  "Userspace": "用户空间",
  "Schedutil": "调度器联动",
  "Relaxed": "舒缓",
  "Moderate": "适中",
  "Aggressive": "激进",
  "Fast": "快速",
  "Compatible": "兼容",
  "Fake": "模拟休眠",
  "Deep": "深度休眠",
  "Plasma Mobile": "Plasma 移动版",
  "Plasma Desktop": "Plasma 桌面版",
  "Steam Deck": "Steam Deck",
  "Xbox 360": "Xbox 360",
  "DualSense": "DualSense",
  "Powersave": "节能",
  "App {id}": "应用 {id}",
  "EDIT POWER PROFILE": "编辑功耗方案",
  "PROFILE SETTINGS": "方案设置",
  "Fan Curve": "风扇曲线",
  "CPU Governor": "CPU 调频策略",
  "CPU Underclock": "CPU 降频幅度",
  "CPU Max (%)": "CPU 最高频率 (%)",
  "GPU Min (%)": "GPU 最低频率 (%)",
  "GPU Max (%)": "GPU 最高频率 (%)",
  "Reset to Default": "恢复默认设置",
  "Controller": "控制器",
  "Emulation": "模拟类型",
  "Launch Calibration": "启动校准",
  "System": "系统",
  "Enable SSH": "启用 SSH",
  "OS Version": "系统版本",
  "ABL Version": "ABL 版本",
  "unknown": "未知",
  "Experimental": "实验性功能",
  "Sleep Mode": "休眠模式",
  "Desktop Mode": "桌面模式",
  "USB File Transfer": "USB 文件传输",
  "Enabled until shutdown": "已启用，关机后停用",
  "Automatic ABL Updates": "自动更新 ABL",
  "Updates during shutdown": "关机时更新",
  "Could not change desktop mode": "无法更改桌面模式",
  "Could not change sleep mode": "无法更改休眠模式",
  "Checking controller...": "正在检测控制器……",
  "This device can't save calibration, but you can check stick and trigger response here.": "此设备无法保存校准数据，但你仍可在此检查摇杆和扳机响应。",
  "Move both sticks in full circles and fully press both triggers, then Save.": "将两个摇杆沿边缘完整转圈，并将两个扳机完全按下，然后保存。",
  "Press Start, then move sticks and triggers through full range.": "选择“开始校准”，然后让摇杆和扳机完成整个行程。",
  "Left Stick": "左摇杆",
  "Right Stick": "右摇杆",
  "Close": "关闭",
  "Save Calibration": "保存校准",
  "Start Calibration": "开始校准",
  "Reset to Defaults": "恢复默认校准",
  "Invalid entry: {value}": "无效项目：{value}",
  "Invalid range: {value}": "无效范围：{value}",
  "No such CPU: {value}": "不存在 CPU {value}",
  "Duplicate CPU: {value}": "CPU {value} 重复",
  "Enter cores, e.g. 7,3-6": "请输入核心，例如 7,3-6",
  "TSO Enabled": "启用 TSO",
  "X87 Reduced Precision": "降低 X87 精度",
  "Multiblock": "多块模式",
  "Vector TSO Enabled": "启用向量 TSO",
  "Memcpy Set TSO Enabled": "启用 Memcpy/Set TSO",
  "Half Barrier TSO Enabled": "启用半屏障 TSO",
  "Host Vulkan": "主机 Vulkan",
  "Host OpenGL": "主机 OpenGL",
  "Host ALSA": "主机 ALSA",
  "Host DRM": "主机 DRM",
  "Host Wayland": "主机 Wayland",
  "Restores Armada defaults for launch options, resolution, and compatibility across all games.": "将所有游戏的启动选项、分辨率和兼容性设置恢复为 Armada 默认值。",
  "Reset All Games": "重置所有游戏",
  "Cancel": "取消",
  "Restores Armada defaults for {game}. Custom launch options and per-game settings will be removed.": "将 {game} 恢复为 Armada 默认设置，并删除自定义启动选项和游戏专用设置。",
  "Reset Game": "重置游戏",
  "Gamescope must restart before this change takes effect. This closes any running game and restarts Steam.": "此更改需要重启 Gamescope 才能生效。正在运行的游戏将关闭，Steam 也会重启。",
  "Restart Game Mode": "重启游戏模式",
  "Later": "稍后",
  "Invalid name: must be non-empty, no '='": "名称无效：不能为空，也不能包含“=”",
  "Name": "名称",
  "Value": "值",
  "Save": "保存",
  "Delete": "删除",
  "Resolution override is unavailable": "分辨率覆盖功能不可用",
  "Failed to set resolution override": "设置分辨率覆盖失败",
  "Failed to set default resolution": "设置默认分辨率失败",
  "this game": "此游戏",
  "Applying...": "正在应用……",
  "Applied to running game": "已应用到正在运行的游戏",
  "Restarting Game Mode...": "正在重启游戏模式……",
  "Restart failed: {error}": "重启失败：{error}",
  "Game": "游戏",
  "CPU Cores": "CPU 核心",
  "Custom cores (ordered, e.g. 7,3-6)": "自定义核心（按顺序，例如 7,3-6）",
  "Wine CPU Topology": "Wine CPU 拓扑",
  "Nice": "Nice 优先级",
  "Gamescope": "Gamescope",
  "Custom cores": "自定义核心",
  "CPU Realtime Scheduling": "CPU 实时调度",
  "Vulkan Realtime Queue": "Vulkan 实时队列",
  "CPU Scheduler": "CPU 调度器",
  "Re-apply to Running Game": "重新应用到正在运行的游戏",
  "Status": "状态",
  "Default Variables": "默认变量",
  "Per-Game Variables": "游戏专用变量",
  "+ Add Variable": "+ 添加变量",
  "EDIT GAME PROFILE": "编辑游戏配置",
  "Compatibility changes apply on next launch": "兼容性更改将在下次启动游戏时生效",
  "Default Proton": "默认 Proton",
  "Choose a Proton": "选择 Proton",
  "{tool} is no longer installed. Choose a new default for your games.": "{tool} 已不再安装。请为游戏选择新的默认工具。",
  "Apply to New Games": "应用于新游戏",
  "Game Resolution": "游戏分辨率",
  "Compatibility Tool": "兼容性工具",
  "FEX Preset": "FEX 预设",
  "ADVANCED": "高级设置",
  "Hide Performance": "隐藏性能调优",
  "Hide Host Thunks": "隐藏主机 Thunk",
  "Host Thunks": "主机 Thunk",
  "Hide Environment": "隐藏环境变量",
  "Environment": "环境变量",
  "Resetting...": "正在重置……",
  "Armada Fans": "Armada 风扇",
  "SAVE": "保存",
  "Saving...": "正在保存……",
  "Save Changes": "保存更改",
  "Revert Changes": "撤销更改",
  "You have unsaved changes.": "有尚未保存的更改。",
  "Create Curve": "新建风扇曲线",
  "Curve Name": "曲线名称",
  "Letters, numbers, spaces, hyphens, and underscores are supported.": "支持字母、数字、空格、连字符和下划线。",
  "A curve named “{name}” already exists.": "已存在名为“{name}”的曲线。",
  "Base Curve": "基础曲线",
  "The new curve starts as a copy of the selected base curve. Changes remain unsaved until Save Changes is pressed.": "新曲线将复制所选基础曲线。选择“保存更改”前，所有更改均不会写入磁盘。",
  "EDIT CURVE": "编辑风扇曲线",
  "Curve": "风扇曲线",
  "No fan curves found": "未找到风扇曲线",
  "Used by: {profiles}": "应用于：{profiles}",
  "Not assigned to any profile": "未分配给任何方案",
  "FAN RESPONSIVENESS": "风扇响应",
  "Ramp Up": "加速速率",
  "How fast the fan speeds up per ~3-second tick as the target rises.": "目标转速升高时，风扇每约 3 秒的加速幅度。",
  "Ramp Down": "减速速率",
  "How fast the fan slows down per ~3-second tick once the target drops.": "目标转速降低时，风扇每约 3 秒的减速幅度。",
  "Temperature Smoothing (%)": "温度平滑 (%)",
  "Evens out the temperature reading itself before it reaches the curve, so brief spikes don't yank the target around.": "在温度数据进入曲线前进行平滑，避免短时温度尖峰导致目标转速剧烈变化。",
  "Minimum Fan Speed (%)": "最低风扇转速 (%)",
  "The lowest speed Armada allows. Fan Stop forces it to 0%.": "Armada 允许的最低转速；启用风扇停转后会强制设为 0%。",
  "MANAGE CURVES": "管理风扇曲线",
  "Curve To Delete": "要删除的曲线",
  "Tap Again To Confirm Delete": "再按一次确认删除",
  "Delete Curve": "删除曲线",
  "No curves are eligible for deletion -- only a curve with no factory default that isn't assigned to a profile on the Power tab can be removed.": "没有可删除的曲线。只能删除非出厂默认且未分配给“功耗”页任何方案的曲线。",
  "POINTS": "曲线节点",
  "Drag a point, or press A to steer it with the D-Pad. LB/RB switches points; B exits.": "拖动节点，或按 A 后用方向键调整。LB/RB 切换节点，B 退出。",
  "Reset Curve To Factory": "恢复出厂曲线",
  "Nothing here is written to disk until you press Save Changes.": "选择“保存更改”前，此处内容不会写入磁盘。",
  "Also adjustable via the Minimum Fan Speed slider in Fan Responsiveness.": "也可通过“风扇响应”中的“最低风扇转速”滑块调整。",
  "⚠ Below the Minimum Fan Speed floor -- tap to lower it to match": "⚠ 低于最低风扇转速限制——按下可将限制降低到匹配值",
  "Drag a point, or press A to steer it with the D-Pad. LB/RB switches points; B exits. Advanced editing uses raw {min}-{max} PWM.": "拖动节点，或按 A 后用方向键调整。LB/RB 切换节点，B 退出。高级编辑使用原始 {min}-{max} PWM 值。",
  "Fan Stop": "风扇停转",
  "Fan off below the set temperature.": "低于设定温度时停止风扇。",
  "Stop Until (°C)": "停转温度上限 (°C)",
  "The 0% minimum applies globally while Fan Stop is enabled.": "启用风扇停转期间，全局最低转速为 0%。",
  "Fullscreen Editor": "全屏编辑器",
  "Hide Points": "隐藏节点",
  "Edit Curve Points": "编辑曲线节点",
  "Add Point": "添加节点",
  "Temperature (°C)": "温度 (°C)",
  "Edit Point": "编辑节点",
  "Stop Editing": "停止编辑",
  "FAN STOPPED": "风扇已停转",
  "D-Pad moves point {current} of {total} · LB/RB switches points · B stops": "方向键移动第 {current}/{total} 个节点 · LB/RB 切换节点 · B 停止编辑",
  "Could not load RGB lighting": "无法读取 RGB 灯光设置",
  "Could not change RGB lighting": "无法更改 RGB 灯光设置",
  "RGB Lighting": "RGB 灯光",
  "Enabled": "启用",
  "Brightness": "亮度",
  "Color": "颜色",
} as const;

export type TranslationKey = keyof typeof zhCN;
type Variables = Record<string, string | number>;

export function localeFromLanguage(language: unknown): Locale | null {
  if (typeof language !== "string") return null;
  const normalized = language.trim().toLowerCase().split("_").join("-");
  if (["schinese", "steamchina-schinese", "zh", "zh-cn", "zh-hans", "zh-sg"].includes(normalized)) return "zh-CN";
  return normalized ? "en" : null;
}

function firstLocale(values: readonly unknown[] | undefined): Locale | null {
  for (const value of values || []) {
    const locale = localeFromLanguage(value);
    if (locale) return locale;
  }
  return null;
}

export function resolveLocale({
  steamLanguage,
  deckyLocales,
  browserLanguages,
}: {
  steamLanguage?: unknown;
  deckyLocales?: readonly unknown[];
  browserLanguages?: readonly unknown[];
}): Locale {
  return localeFromLanguage(steamLanguage)
    || firstLocale(deckyLocales)
    || firstLocale(browserLanguages)
    || "en";
}

export function detectLocaleFromEnvironment(): Locale {
  let deckyLocales: readonly unknown[] | undefined;
  let browserLanguages: readonly unknown[] | undefined;
  try {
    deckyLocales = window.LocalizationManager?.m_rgLocalesToUse;
  } catch (error) {
  }
  try {
    browserLanguages = navigator.languages || [navigator.language];
  } catch (error) {
  }
  return resolveLocale({ deckyLocales, browserLanguages });
}

let currentLocale: Locale = "en";

export function setCurrentLocale(locale: Locale): void {
  currentLocale = locale;
}

function interpolate(text: string, variables?: Variables): string {
  if (!variables) return text;
  return Object.entries(variables).reduce(
    (result, [key, value]) => result.split(`{${key}}`).join(String(value)),
    text,
  );
}

export function translate(locale: Locale, key: TranslationKey, variables?: Variables): string {
  const text = locale === "zh-CN" ? zhCN[key] : key;
  return interpolate(text, variables);
}

export function t(key: TranslationKey, variables?: Variables): string {
  return translate(currentLocale, key, variables);
}

export function translateLabelForLocale(locale: Locale, label: string): string {
  if (locale !== "zh-CN") return label;
  const exact = zhCN[label as TranslationKey];
  if (exact) return exact;
  for (const prefix of ["Big Cores", "Prime Cores", "Little Cores"] as const) {
    if (label.startsWith(`${prefix} (`)) return label.replace(prefix, zhCN[prefix]);
  }
  return label;
}

export function translateLabel(label: string): string {
  return translateLabelForLocale(currentLocale, label);
}
