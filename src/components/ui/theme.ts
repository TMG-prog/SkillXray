// Shared design tokens supporting both Light and Dark themes

export const colors = {
  light: {
    background: "#F2FFD9",
    surface: "#FFFFFF",
    surfaceMuted: "#F0F4E8",
    border: "#DCE5D2",

    textPrimary: "#071412",
    textSecondary: "#5F6B67",
    textMuted: "#8A9691",

    accent: "#18D8D0",
    accentSoft: "#D9FFFA",

    // Button gradient
    buttonGradient: ["#D9FFB8", "#18D8D0"] as const,

    progressTrack: "#DCE5D2",
    progressFill: "#18D8D0",

    severityHigh: "#EF4444",
    severityMedium: "#F59E0B",
    severityLow: "#18B981",
  },

  dark: {
    background: "#020B09",
    surface: "#06110F",
    surfaceMuted: "#0B1916",
    border: "#172722",

    textPrimary: "#F8FAF9",
    textSecondary: "#A7B5B1",
    textMuted: "#6F7D79",

    accent: "#18D8D0",
    accentSoft: "#063B37",

    // Mint → cyan gradient from the screenshot
    buttonGradient: ["#D9FFB8", "#18D8D0"] as const,

    progressTrack: "#172722",
    progressFill: "#18D8D0",

    severityHigh: "#EF4444",
    severityMedium: "#F59E0B",
    severityLow: "#18B981",
  },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
};

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999,
};

export const typography = {
  h1: {
    fontSize: 22,
    fontWeight: "700" as const,
  },

  h2: {
    fontSize: 18,
    fontWeight: "700" as const,
  },

  body: {
    fontSize: 15,
    fontWeight: "400" as const,
  },

  caption: {
    fontSize: 13,
    fontWeight: "400" as const,
  },
};
