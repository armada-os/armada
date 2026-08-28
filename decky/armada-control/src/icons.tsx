import type { ReactNode } from "react";

function Icon({ path, size = 20 }: { path: ReactNode; size?: number }) {
  return (
    <svg
      style={{ display: "block" }}
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
  Compatibility: (
    <Icon
      size={TAB_ICON_SIZE}
      path={
        <>
          <line x1="6" x2="10" y1="11" y2="11" />
          <line x1="8" x2="8" y1="9" y2="13" />
          <line x1="15" x2="15.01" y1="12" y2="12" />
          <line x1="18" x2="18.01" y1="10" y2="10" />
          <path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z" />
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
  Advanced: (
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
