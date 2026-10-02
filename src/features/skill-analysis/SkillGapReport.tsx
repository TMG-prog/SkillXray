import { View, Text, StyleSheet } from "react-native";

// Renders extracted skills vs. target-role requirements and the resulting
// SkillGap list produced by the Skill Gap Analysis module.
export function SkillGapReport() {
  return (
    <View style={styles.section}>
      <Text style={styles.title}>Skill Gap Analysis</Text>
      {/* TODO: fetch SkillAnalysis + SkillGaps for selected resume/role pair */}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { padding: 16 },
  title: { fontSize: 20, fontWeight: "600", marginBottom: 16 },
});
