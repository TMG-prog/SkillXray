
 // Shared design tokens for a professional resume analyzer

export const colors = {
  light: {
    background: "#F4F7FB",
    surface: "#FFFFFF",
    surfaceMuted: "#EDF2F8",
    border: "#DCE4EE",

    textPrimary: "#172B4D",
    textSecondary: "#59697D",
    textMuted: "#8996A7",

    accent: "#5279AD",
    accentSoft: "#E3ECF8",

    // Subtle navy-to-steel-blue gradient
    buttonGradient: ["#304F7C", "#5279AD"] as const,

    progressTrack: "#DFE7F1",
    progressFill: "#5279AD",

    severityHigh: "#C75C5C",
    severityMedium: "#C28A43",
    severityLow: "#4E896B",
  },

  dark: {
    background: "#0D1522",
    surface: "#141F30",
    surfaceMuted: "#1C2A3E",
    border: "#2A3A50",

    textPrimary: "#F1F5FA",
    textSecondary: "#B1BED0",
    textMuted: "#7F8DA2",

    accent: "#83A9DB",
    accentSoft: "#213652",

    // Muted blue gradient
    buttonGradient: ["#5279AD", "#3F6597"] as const,

    progressTrack: "#2A3A50",
    progressFill: "#83A9DB",

    severityHigh: "#E47C7C",
    severityMedium: "#D8AA68",
    severityLow: "#7FB896",
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
