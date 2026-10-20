import { Pressable, Text, StyleSheet, PressableProps, useColorScheme, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { colors, radius, spacing } from "./theme";

interface Props extends PressableProps {
  label: string;
  variant?: "solid" | "muted";
}

export function PillButton({ label, variant = "solid", style, ...props }: Props) {
  const colorScheme = useColorScheme();
  const theme = colors[colorScheme === "dark" ? "dark" : "light"];
  const isSolid = variant === "solid";

  return (
    <Pressable
      style={({ pressed }) => [
        styles.base,
        !isSolid && { backgroundColor: theme.accentSoft },
        pressed && { opacity: 0.95 },
        style as any,
      ]}
      {...props}
    >
      {isSolid && (
        <LinearGradient
          colors={theme.buttonGradient}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={StyleSheet.absoluteFill}
        />
      )}
      <Text
        style={[
          styles.text,
          { color: isSolid ? theme.onAccent : theme.textPrimary },
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
    borderRadius: radius.round,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden", // clips the gradient to the pill shape
  },
  text: { fontWeight: "600", fontSize: 15 },
});