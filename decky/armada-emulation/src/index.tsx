import { definePlugin } from "@decky/api";
import { Content } from "./Content";

export default definePlugin(() => ({
  name: "Armada Emulation",
  content: <Content />,
  icon: (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="2" y="7" width="20" height="10" rx="5" />
      <path d="M7 10v4" />
      <path d="M5 12h4" />
      <circle cx="16" cy="11" r="0.5" />
      <circle cx="18" cy="13" r="0.5" />
    </svg>
  ),
}));
