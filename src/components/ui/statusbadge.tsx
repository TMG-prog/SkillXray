import { View, Text, StyleSheet } from "react-native";
import { brand } from "./theme";
import type { TrackedCourseStatus } from "@/types";

const CONFIG: Record<TrackedCourseStatus, { label: string; color: string }> = {
  not_started: { label: "Not started", color: brand.muted },
  in_progress: { label: "In progress", color: brand.cyan },
  completed: { label: "Completed", color: brand.mint },
};

export function StatusBadge({ status }: { status: TrackedCourseStatus }) {
  const { label, color } = CONFIG[status];
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={[styles.text, { color }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderWidth: 1,
    borderRadius: 999,
    paddingVertical: 4,
    paddingHorizontal: 10,
    alignSelf: "flex-start",
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  text: { fontSize: 12, fontWeight: "600" },
});