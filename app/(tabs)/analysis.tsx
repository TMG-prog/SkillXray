import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useEffect, useState } from "react";
import { SafeAreaView } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";
import Svg, { Circle, Defs, LinearGradient as SvgGradient, Stop } from "react-native-svg";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { useAppData } from "@/state/appdatacontext";
import { brand, colors, SERIF } from "@/components/ui/theme";
import { AnalysisVisualizations } from "@/features/skill-analysis/AnalysisVisualizations";

type Severity = "high" | "medium" | "low";

const SEVERITY: Record<Severity, { label: string; color: string }> = {
  high: { label: "High", color: colors.dark.severityHigh },
  medium: { label: "Medium", color: colors.dark.severityMedium },
  low: { label: "Low", color: colors.dark.severityLow },
};

type AnalysisTab = "readiness" | "skills" | "market" | "pathways";
const ANALYSIS_TABS: { id: AnalysisTab; label: string; icon: keyof typeof Feather.glyphMap }[] = [
  { id: "readiness", label: "Readiness", icon: "activity" },
  { id: "skills", label: "Skills", icon: "list" },
  { id: "market", label: "Market", icon: "bar-chart-2" },
  { id: "pathways", label: "Pathways", icon: "git-branch" },
];

export default function AnalysisScreen() {
  const router = useRouter();
  const { analysis } = useAppData();
  const [activeTab, setActiveTab] = useState<AnalysisTab>("readiness");
  useEffect(() => setActiveTab("readiness"), [analysis]);

  if (!analysis) {
    return (
      <View style={styles.root}>
        <LinearGradient
          colors={[brand.tint, "transparent"]}
          style={styles.glow}
          pointerEvents="none"
        />
        <SafeAreaView style={styles.safeArea} edges={["top"]}>
          <View style={styles.emptyContainer}>
            <View style={styles.emptyIconCircle}>
              <Feather name="bar-chart-2" size={26} color={brand.cyan} />
            </View>
            <Text style={styles.emptyTitle}>No analysis yet</Text>
            <Text style={styles.emptyMessage}>
              Upload your resume to see how your skills stack up against your target role.
            </Text>
            <Pressable
              onPress={() => router.push("/resume-upload")}
              style={({ pressed }) => [styles.buttonWrap, pressed && { opacity: 0.85 }]}
            >
              <LinearGradient
                colors={[brand.cyan, brand.mint]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.button}
              >
                <Text style={styles.buttonText}>Upload your resume</Text>
              </LinearGradient>
            </Pressable>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  const readinessScore = Math.round(analysis.readiness);
  const gaps = analysis.gaps.map((g) => ({
    skill: g.skill,
    severity: g.severity,
    score: Math.round(g.fill * 100),
  }));

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={[brand.tint, "transparent"]}
        style={styles.glow}
        pointerEvents="none"
      />

      <SafeAreaView style={styles.safeArea} edges={["top"]}>
        <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
          <Text style={styles.roleLabel}>Career readiness · {analysis.targetRole}</Text>

          <LinearGradient
            colors={[brand.cyan, brand.mint]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.scoreBorder}
          >
            <View style={styles.scoreInner}>
              <View style={styles.ring}>
                <Svg width={190} height={190} style={{ transform: [{ rotate: "-90deg" }] }}>
                  <Defs>
                    <SvgGradient id="ring" x1="0" y1="0" x2="1" y2="1">
                      <Stop offset="0" stopColor={brand.cyan} />
                      <Stop offset="1" stopColor={brand.mint} />
                    </SvgGradient>
                  </Defs>
                  <Circle
                    cx={95}
                    cy={95}
                    r={87}
                    stroke={brand.border}
                    strokeWidth={10}
                    fill="none"
                  />
                  <Circle
                    cx={95}
                    cy={95}
                    r={87}
                    stroke="url(#ring)"
                    strokeWidth={10}
                    strokeLinecap="round"
                    strokeDasharray={2 * Math.PI * 87}
                    strokeDashoffset={2 * Math.PI * 87 * (1 - readinessScore / 100)}
                    fill="none"
                  />
                </Svg>
                <Text style={styles.scoreText}>{readinessScore}%</Text>
              </View>

              <Text style={styles.scoreTitle}>Career readiness</Text>
              {analysis.demo && <Text style={styles.demoLabel}>Demo sample score</Text>}
            </View>
          </LinearGradient>

          {analysis.demo && activeTab !== "readiness" && (
            <View style={styles.demoNotice}>
              <Feather name="info" size={16} color={colors.dark.severityMedium} />
              <Text style={styles.demoNoticeText}>
                Demo results only. This sample was not calculated from your resume or target role.
              </Text>
            </View>
          )}

          <View style={styles.tabBar} accessibilityRole="tablist">
            {ANALYSIS_TABS.map((tab) => {
              const selected = activeTab === tab.id;
              return (
                <Pressable
                  key={tab.id}
                  accessibilityRole="tab"
                  accessibilityState={{ selected }}
                  onPress={() => setActiveTab(tab.id)}
                  style={[styles.tab, selected && styles.activeTab]}
                >
                  <Feather name={tab.icon} size={16} color={selected ? brand.onGradient : brand.muted} />
                  <Text style={[styles.tabText, selected && styles.activeTabText]}>{tab.label}</Text>
                </Pressable>
              );
            })}
          </View>

          {activeTab === "skills" && (
            <>
              <AnalysisVisualizations
                view="skills"
                requirements={analysis.requirements}
                relationships={analysis.relationships}
                covered={analysis.covered}
                marketInsights={analysis.marketInsights}
              />
              <Text style={styles.sectionTitle}>Identified gaps</Text>
              {gaps.length ? (
                <View style={styles.gapList}>
                  {gaps.map((item) => {
                    const sev = SEVERITY[item.severity];
                    return (
                      <View key={item.skill} style={styles.gapCard}>
                        <View style={styles.gapHeader}>
                          <Text style={styles.gapSkillName}>{item.skill}</Text>
                          <View style={[styles.badge, { backgroundColor: `${sev.color}22` }]}>
                            <Text style={[styles.badgeText, { color: sev.color }]}>{sev.label}</Text>
                          </View>
                        </View>
                        <View style={styles.track}>
                          <LinearGradient
                            colors={[brand.cyan, brand.mint]}
                            start={{ x: 0, y: 0 }}
                            end={{ x: 1, y: 0 }}
                            style={[styles.fill, { width: `${item.score}%` }]}
                          />
                        </View>
                        <Text style={styles.scoreLabel}>{item.score}% match credit</Text>
                      </View>
                    );
                  })}
                </View>
              ) : (
                <Text style={styles.emptyCovered}>No gaps found for this target role.</Text>
              )}
              <Text style={styles.sectionTitle}>Skills matched</Text>
              <View style={styles.coveredList}>
                {analysis.covered.length ? analysis.covered.map((skill) => (
                  <View key={skill} style={styles.coveredChip}>
                    <Text style={styles.coveredText}>{skill}</Text>
                  </View>
                )) : <Text style={styles.emptyCovered}>No required skills matched this resume.</Text>}
              </View>
              {analysis.warnings.length > 0 && (
                <View style={styles.warningCard}>
                  {analysis.warnings.map((warning) => (
                    <Text key={warning} style={styles.warningText}>{warning}</Text>
                  ))}
                </View>
              )}
              <Pressable
                onPress={() => router.push("/courses")}
                accessibilityRole="button"
                style={({ pressed }) => [styles.buttonWrap, pressed && { opacity: 0.85 }]}
              >
                <LinearGradient
                  colors={[brand.cyan, brand.mint]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.button}
                >
                  <Text style={styles.buttonText}>View recommendations</Text>
                </LinearGradient>
              </Pressable>
            </>
          )}

          {(activeTab === "market" || activeTab === "pathways") && (
            <AnalysisVisualizations
              view={activeTab}
              requirements={analysis.requirements}
              relationships={analysis.relationships}
              covered={analysis.covered}
              marketInsights={analysis.marketInsights}
            />
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: brand.bg },
  safeArea: { flex: 1 },
  glow: { position: "absolute", top: 0, left: 0, right: 0, height: 320 },
  container: { padding: 16, paddingBottom: 40 },

  roleLabel: { color: brand.muted, fontSize: 13, textAlign: "center", marginTop: 12, marginBottom: 16 },
  demoNotice: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    backgroundColor: "#FEF3C7",
    borderRadius: 12,
    padding: 12,
    marginTop: -8,
    marginBottom: 18,
  },
  demoNoticeText: { flex: 1, color: "#78350F", fontSize: 13, lineHeight: 18 },

  scoreBorder: { borderRadius: 20, padding: 1, marginBottom: 20 },
  scoreInner: {
    backgroundColor: brand.surfaceSolid,
    borderRadius: 19,
    paddingVertical: 28,
    paddingHorizontal: 20,
    alignItems: "center",
  },
  ring: { width: 190, height: 190, alignItems: "center", justifyContent: "center", marginBottom: 14 },
  scoreText: { position: "absolute", fontSize: 38, fontWeight: "700", color: brand.text },
  scoreTitle: { fontSize: 18, fontWeight: "700", color: brand.text },
  demoLabel: { fontSize: 12, color: "#78350F", marginTop: 6 },
  tabBar: { flexDirection: "column", gap: 8, marginBottom: 18 },
  tab: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "flex-start",
    gap: 10,
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 12,
    paddingHorizontal: 14,
  },
  activeTab: { backgroundColor: brand.cyan, borderColor: brand.cyan },
  tabText: { color: brand.muted, fontSize: 14, fontWeight: "600" },
  activeTabText: { color: brand.onGradient },

  sectionTitle: { fontSize: 18, fontWeight: "700", color: brand.text, marginBottom: 16 },
  gapList: { gap: 10 },
  gapCard: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 16,
  },
  gapHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  gapSkillName: { fontSize: 16, fontWeight: "600", color: brand.text },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  badgeText: { fontSize: 13, fontWeight: "700" },

  track: { height: 6, borderRadius: 3, backgroundColor: brand.border, overflow: "hidden" },
  fill: { height: 6, borderRadius: 3 },
  scoreLabel: { fontSize: 13, color: brand.muted, marginTop: 8 },
  coveredList: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  coveredChip: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  coveredText: { color: brand.text, fontSize: 13, fontWeight: "600" },
  emptyCovered: { color: brand.muted, fontSize: 14 },
  warningCard: {
    marginTop: 20,
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 16,
    gap: 8,
  },
  warningText: { color: brand.muted, fontSize: 13, lineHeight: 19 },

  buttonWrap: { marginTop: 28, borderRadius: 999, overflow: "hidden" },
  button: {
    minHeight: 58,
    paddingVertical: 16,
    paddingHorizontal: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonText: { color: brand.onGradient, fontSize: 16, fontWeight: "700" },

  emptyContainer: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 32 },
  emptyIconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: brand.tint,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },
  emptyTitle: { fontFamily: SERIF, fontSize: 24, color: brand.text, textAlign: "center", marginBottom: 10 },
  emptyMessage: { fontSize: 14, lineHeight: 20, color: brand.muted, textAlign: "center", marginBottom: 8 },
});