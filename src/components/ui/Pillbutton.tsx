import { Pressable, Text, StyleSheet, PressableProps, useColorScheme } from "react-native";
import { colors, radius, spacing } from "./theme";

interface Props extends PressableProps {
  label: string;
  variant?: "solid" | "muted";
}

// Matches the pill-shaped buttons with dynamic light/dark theme support.
export function PillButton({ label, variant = "solid", style, ...props }: Props) {
  const colorScheme = useColorScheme();
  const themeColors = colors[colorScheme === "dark" ? "dark" : "light"];

  return (
    <Pressable
      style={({ pressed }) => [
        styles.base,
        variant === "solid" 
          ? { backgroundColor: themeColors.accent } 
          : { backgroundColor: themeColors.accentSoft },
        pressed && { opacity: 0.85 },
        style as any,
      ]}
      {...props}
    >
      <Text 
        style={[
          styles.text, 
          { 
            color: variant === "solid" 
              ? (colorScheme === "dark" ? "#0A0F0D" : "#FFFFFF") // Dark text on bright mint in dark mode for contrast
              : themeColors.textPrimary 
          }
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  text: { 
    fontWeight: "600", 
    fontSize: 15,
  },
});