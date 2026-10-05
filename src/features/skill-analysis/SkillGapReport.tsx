import { View, Text, Pressable, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import Svg, { Circle } from "react-native-svg";
import { useAppData } from "@/state/appdatacontext";
import { brand, SERIF } from "@/components/ui/brand";

const ACCENT = "#25D9D0";
const ACCENT_DARK = "#06201F";

export function SkillGapReport() {
  const router = useRouter();
  const { analysis } = useAppData();

  if (!analysis) {
    return (
      <View style={styles.emptyContainer}>
        <View style={styles.emptyIconCircle}>
          <Feather name="bar-chart-2" size={26} color={ACCENT} />
        </View>
        <Text style={styles.emptyTitle}>No analysis yet</Text>
        <Text style={styles.emptyMessage}>
          Upload your resume to see how your skills stack up against your target role.
        </Text>
        <Pressable style={styles.emptyButton} onPress={() => router.push("/resume-upload")}>
          <Text style={styles.emptyButtonText}>Upload your resume</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.section}>
      <Text style={styles.title}>Skill Gap Analysis</Text>

      <View style={styles.pill}>
        <Text style={styles.pillText}>
          You meet about {Math.round(analysis.readiness)}% of requirements
        </Text>
      </View>

      <View style={styles.ringWrap}>
        <CircularProgress percent={analysis.readiness} />
        <Text style={styles.ringLabel}>Career Readiness</Text>
      </View>

      <View style={{ marginTop: 24 }}>
        <Text style={styles.sectionHeader}>Identified Gaps</Text>
        {analysis.gaps.map((gap) => (
          <View key={gap.skill} style={styles.gapRow}>
            <View style={styles.gapHeaderRow}>
              <Text style={styles.gapSkill}>{gap.skill}</Text>
              <Text style={[styles.severityText, { color: SEVERITY_COLOR[gap.severity] }]}>
                {gap.severity}
              </Text>
            </View>
            <View style={styles.track}>
              <View style={[styles.fill, { width: `${Math.max(0, Math.min(1, gap.fill)) * 100}%` }]} />
            </View>
          </View>
        ))}
      </View>

      <Pressable style={styles.recButton} onPress={() => router.push("/(tabs)/courses")}>
        <Text style={styles.recButtonText}>View Recommendations</Text>
      </Pressable>
    </View>
  );
}

const SEVERITY_COLOR: Record<string, string> = {
  high: "#F87171",
  medium: "#FBBF24",
  low: "#34D399",
};

function CircularProgress({ percent, size = 140, strokeWidth = 12 }: { percent: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - percent / 100);

  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <Svg width={size} height={size}>
        <Circle cx={size / 2} cy={size / 2} r={radius} stroke="rgba(255,255,255,0.1)" strokeWidth={strokeWidth} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={ACCENT}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={offset}
          strokeLinecap="round"
          rotation="-90"
          origin={`${size / 2}, ${size / 2}`}
        />
      </Svg>
      <View style={StyleSheet.absoluteFill}>
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <Text style={{ fontSize: 24, fontWeight: "700", color: brand.text }}>{Math.round(percent)}%</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { padding: 16, paddingBottom: 40 },
  title: { fontFamily: SERIF, fontSize: 26, color: brand.text, textAlign: "center", marginBottom: 16 },
  pill: {
    backgroundColor: "rgba(255,255,255,0.06)",
    borderRadius: 999,
    paddingVertical: 8,
    paddingHorizontal: 16,
    alignItems: "center",
    marginBottom: 24,
  },
  pillText: { fontSize: 13, color: brand.muted },
  ringWrap: { alignItems: "center", gap: 8 },
  ringLabel: { fontSize: 17, fontWeight: "700", color: brand.text },
  sectionHeader: { fontSize: 16, fontWeight: "700", color: brand.text, marginBottom: 12 },
  gapRow: { marginBottom: 16 },
  gapHeaderRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 6 },
  gapSkill: { fontSize: 15, fontWeight: "600", color: brand.text },
  severityText: { fontSize: 13, fontWeight: "600", textTransform: "lowercase" },
  track: { height: 6, borderRadius: 999, backgroundColor: "rgba(255,255,255,0.1)", overflow: "hidden" },
  fill: { height: "100%", borderRadius: 999, backgroundColor: ACCENT },
  recButton: { marginTop: 8, backgroundColor: "rgba(255,255,255,0.08)", borderRadius: 999, paddingVertical: 14, alignItems: "center" },
  recButtonText: { color: brand.text, fontWeight: "700", fontSize: 15 },

  emptyContainer: { alignItems: "center", paddingVertical: 64, paddingHorizontal: 24 },
  emptyIconCircle: {
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: "rgba(37,217,208,0.12)",
    alignItems: "center", justifyContent: "center", marginBottom: 16,
  },
  emptyTitle: { fontFamily: SERIF, fontSize: 20, color: brand.text, textAlign: "center", marginBottom: 8 },
  emptyMessage: { fontSize: 14, lineHeight: 20, color: brand.muted, textAlign: "center", marginBottom: 20 },
  emptyButton: { backgroundColor: ACCENT, borderRadius: 999, paddingVertical: 12, paddingHorizontal: 24 },
  emptyButtonText: { color: ACCENT_DARK, fontWeight: "700", fontSize: 14 },
});
