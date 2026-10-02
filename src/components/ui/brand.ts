import { Platform } from "react-native";

// Shared palette for login, home and recommendations. Drop this into @/components/ui/theme when ready.
export const brand = {
  bg: "#03110F",
  surface: "rgba(8, 26, 24, 0.88)",
  surfaceSolid: "#071A18",
  border: "rgba(255,255,255,0.10)",
  text: "#EEF7F4",
  muted: "#8FA9A4",
  cyan: "#25D9D0",
  mint: "#C6F3A8",
  tint: "rgba(37,217,208,0.12)",
  onGradient: "#04211E",
} as const;

export const SERIF = Platform.select({ ios: "Georgia", android: "serif", default: "serif" });