import type { ReactNode } from "react";

function Icon({ path }: { path: ReactNode }) {
  return (
    <svg
      style={{ display: "block" }}
      width="20"
      height="20"
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

function StateIcon({ path }: { path: ReactNode }) {
  return (
    <svg
      style={{ display: "block" }}
      width="16"
      height="16"
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

export const searchIcon = <Icon path={<><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>} />;

export const stateIcons: Record<string, ReactNode> = {
  installed: <StateIcon path={<path d="M20 6 9 17l-5-5" />} />,
  update: (
    <StateIcon
      path={
        <>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" x2="12" y1="15" y2="3" />
        </>
      }
    />
  ),
  error: (
    <StateIcon
      path={
        <>
          <circle cx="12" cy="12" r="10" />
          <line x1="12" x2="12" y1="8" y2="12" />
          <line x1="12" x2="12.01" y1="16" y2="16" />
        </>
      }
    />
  ),
};

// Panel controls; catalog sections bring their own icons.
export const addIcon = (
  <Icon
    path={
      <>
        <path d="M5 12h14" />
        <path d="M12 5v14" />
      </>
    }
  />
);
