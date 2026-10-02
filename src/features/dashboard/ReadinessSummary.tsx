import { View, Text, StyleSheet, useColorScheme } from "react-native";
import { colors, typography } from "@/components/ui/theme"; // Adjust path if needed

// Shows the Career Readiness Index + quick links, per the dashboard wireframe.
export function ReadinessSummary() {
  const colorScheme = useColorScheme();
  const themeColors = colors[colorScheme === "dark" ? "dark" : "light"];

  return (
    <View style={styles.section}>
      <Text style={[styles.title, { color: themeColors.textPrimary }]}>
        Your Career Readiness
      </Text>
      {/* TODO: fetch latest SkillAnalysis for the current user */}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { 
    padding: 16, 
  },
  title: {
    fontSize: typography.h1.fontSize,
    fontWeight: typography.h1.fontWeight,
    marginBottom: 16,
  },
});
