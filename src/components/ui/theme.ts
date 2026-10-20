import { Platform } from "react-native";

// Shared design tokens for Light and Dark themes
export const colors = {
  light: {
    background: "#F4F7FA",
    surface: "#FFFFFF",
    surfaceMuted: "#EAF0F5",
    border: "#DCE5ED",

    textPrimary: "#0D1B2A",
    textSecondary: "#4A5D73",
    textMuted: "#73889F",

    // Precision tech accent
    accent: "#007A87",
    accentSoft: "#D8F3F5",

    buttonGradient: ["#0D1B2A", "#1B3A4B"] as const,
    buttonText: "#020202",

    accentGradient: ["#007A87", "#00A8B5"] as const,
    onAccent: "#ffffff",

    progressTrack: "#DCE5ED",
    progressFill: "#007A87",

    // Skill Proficiency / Severity Tiers
    expert: "#0E8345",
    intermediate: "#B87A00",
    beginner: "#526579",
    
    severityHigh: "#D93838",
    severityMedium: "#C47D00",
    severityLow: "#0E8345",

    overlay: "rgba(13, 27, 42, 0.45)",
    inputBackground: "#F8FAFC",
    disabled: "#AAB7C4",
  },

  dark: {
    background: "#050B14", 
    surface: "#0D1926",
    surfaceMuted: "#142538",
    border: "#1F354D",

    textPrimary: "#F1F6FC",
    textSecondary: "#A3B6CC",
    textMuted: "#768EA6",

    // Electric cyan/teal for glowing diagnostics
    accent: "#00E5FF",
    accentSoft: "#0A333B",

    buttonGradient: ["#007A87", "#09646b"] as const,
    buttonText: "#060606",

    accentGradient: ["#00E5FF", "#00B4D8"] as const,
    onAccent: "#050B14",

    progressTrack: "#1F354D",
    progressFill: "#00E5FF",

    // Skill Proficiency / Severity Tiers (vibrant for dark backgrounds)
    expert: "#00F59B",
    intermediate: "#FFC233",
    beginner: "#768EA6",

    severityHigh: "#FF6B6B",
    severityMedium: "#FFD166",
    severityLow: "#00F59B",

    overlay: "rgba(0, 0, 0, 0.70)",
    inputBackground: "#09131E",
    disabled: "#3A4F66",
  },
};

// SkillXRay specialized chart / metric palette
export const skillColors = {
  missing: "#D93838",
  partial: "#C47D00",
  matched: "#0E8345",
  radarStroke: "#00E5FF",
  radarFill: "rgba(0, 229, 255, 0.15)",
};

// Spacing scale
export const spacing = {
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 40,
  xxxl: 56,
};

// Consistent corner radii
export const radius = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  round: 999,
};

// Typography
export const typography = {
  display: {
    fontSize: 34,
    fontWeight: "800" as const,
    letterSpacing: -1,
    lineHeight: 42,
  },
  h1: {
    fontSize: 26,
    fontWeight: "700" as const,
    letterSpacing: -0.6,
    lineHeight: 32,
  },
  h2: {
    fontSize: 20,
    fontWeight: "700" as const,
    letterSpacing: -0.4,
    lineHeight: 26,
  },
  h3: {
    fontSize: 16,
    fontWeight: "600" as const,
    letterSpacing: -0.2,
    lineHeight: 22,
  },
  bodyLarge: {
    fontSize: 16,
    fontWeight: "400" as const,
    lineHeight: 24,
  },
  body: {
    fontSize: 14,
    fontWeight: "400" as const,
    lineHeight: 20,
  },
  bodyMedium: {
    fontSize: 14,
    fontWeight: "500" as const,
    lineHeight: 20,
  },
  caption: {
    fontSize: 12,
    fontWeight: "400" as const,
    lineHeight: 16,
  },
  label: {
    fontSize: 11,
    fontWeight: "700" as const,
    letterSpacing: 0.8,
  },
  code: {
    fontSize: 12,
    fontWeight: "600" as const,
    fontFamily: Platform.select({ ios: "Courier", android: "monospace", default: "monospace" }),
  },
};

// Subtle elevation & Advanced Neon Glows for Dark Mode
export const shadow = {
  subtle: Platform.select({
    ios: { shadowColor: "#000000", shadowOpacity: 0.06, shadowRadius: 8, shadowOffset: { width: 0, height: 2 } },
    android: { elevation: 2 },
    default: {},
  }),
  card: Platform.select({
    ios: { shadowColor: "#000000", shadowOpacity: 0.1, shadowRadius: 16, shadowOffset: { width: 0, height: 6 } },
    android: { elevation: 4 },
    default: {},
  }),
  glow: Platform.select({
    ios: { shadowColor: "#00E5FF", shadowOpacity: 0.25, shadowRadius: 12, shadowOffset: { width: 0, height: 0 } },
    android: { elevation: 6 },
    default: {},
  }),
};

// Auth and landing screen palette (Maintained for backwards-compatibility)
export const brand = {
  bg: "#F4F7FA",
  surface: "#FFFFFF",
  surfaceSolid: "#FFFFFF",
  border: "#DCE5ED",

  text: "#0D1B2A",
  muted: "#73889F",

  cyan: "#007A87",
  mint: "#66a6aa",
  tint: "rgba(0, 122, 135, 0.15)",

  gradientStart: "#0D1B2A",
  gradientEnd: "#1B3A4B",
  onGradient: "#FFFFFF",
} as const;

export const SERIF = Platform.select({
  ios: "Georgia",
  android: "serif",
  default: "serif",
});