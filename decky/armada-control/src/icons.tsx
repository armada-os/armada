import type { ReactNode } from "react";

function Icon({ path, size = 20 }: { path: ReactNode; size?: number }) {
  return (
    <svg
      className="armada-icon"
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {path}
    </svg>
  );
}

const TAB_ICON_SIZE = 18;

export const tabIcons = {
  Controller: (
    <Icon size={TAB_ICON_SIZE} path={<>
      <path d="M6 6h12c2 0 4 8 4 11a3 3 0 0 1-5 2l-3-3h-4l-3 3a3 3 0 0 1-5-2c0-3 2-11 4-11Z" />
      <path d="M6 10v4m-2-2h4m8-1h.01m3 3h.01" />
    </>} />
  ),
  Experimental: (
    <Icon size={TAB_ICON_SIZE} path={<>
      <path d="M9 3h6m-5 0v7L4 20a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1l-6-10V3M7 15h10" />
    </>} />
  ),
  About: (
    <Icon size={TAB_ICON_SIZE} path={<>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6m0-10h.01" />
    </>} />
  ),
  Compatibility: (
    <Icon
      size={TAB_ICON_SIZE}
      path={
        <>
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="M3 9h18M7 6.5h.01M10 6.5h.01M8 13v4m-2-2h4m5-1h.01m3 3h.01" />
        </>
      }
    />
  ),
  Power: (
    <Icon
      size={TAB_ICON_SIZE}
      path={
        <>
          <path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" />
        </>
      }
    />
  ),
  // "fan" icon from Lucide (https://lucide.dev), ISC License.
  Fans: (
    <Icon
      size={TAB_ICON_SIZE}
      path={
        <>
          <path d="M10.827 16.379a6.082 6.082 0 0 1-8.618-7.002l5.412 1.45a6.082 6.082 0 0 1 7.002-8.618l-1.45 5.412a6.082 6.082 0 0 1 8.618 7.002l-5.412-1.45a6.082 6.082 0 0 1-7.002 8.618l1.45-5.412Z" />
          <path d="M12 12v.01" />
        </>
      }
    />
  ),
  // "lightbulb" icon from Lucide (https://lucide.dev), ISC License.
  RGB: (
    <Icon
      size={TAB_ICON_SIZE}
      path={
        <>
          <path d="M9 18h6" />
          <path d="M10 22h4" />
          <path d="M15.09 14c.18-.88.65-1.39 1.41-2.25A6 6 0 0 0 9.33 2.35a6 6 0 0 0-1.83 9.4c.75.85 1.23 1.37 1.41 2.25" />
          <path d="M9 14h6" />
        </>
      }
    />
  ),
  DeviceSettings: (
    <Icon
      size={TAB_ICON_SIZE}
      path={
        <>
          <path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915" />
          <circle cx="12" cy="12" r="3" />
        </>
      }
    />
  ),
};
