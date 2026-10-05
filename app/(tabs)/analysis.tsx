import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";
import Svg, { Circle, Defs, LinearGradient as SvgGradient, Stop } from "react-native-svg";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { useAppData } from "@/state/appdatacontext";
import { brand, SERIF } from "@/components/ui/brand";

type Severity = "high" | "medium" | "low";

const SEVERITY: Record<Severity, { label: string; color: string }> = {
  high: { label: "High", color: "#FF8F86" },
  medium: { label: "Medium", color: "#F2C879" },
  low: { label: "Low", color: brand.mint },
};

const RING = 124;
const STROKE = 8;
const RADIUS = (RING - STROKE) / 2;
const CIRC = 2 * Math.PI * RADIUS;

export default function AnalysisScreen() {
  const router = useRouter();
  const { analysis } = useAppData();

  if (!analysis) {
    return (
      <View style={styles.root}>
        <LinearGradient
          colors={["rgba(37,217,208,0.22)", "rgba(37,217,208,0)"]}
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
        colors={["rgba(37,217,208,0.22)", "rgba(37,217,208,0)"]}
        style={styles.glow}
        pointerEvents="none"
      />

      <SafeAreaView style={styles.safeArea} edges={["top"]}>
        <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
          <Text style={styles.screenTitle}>Skill gap analysis</Text>

          <LinearGradient
            colors={["rgba(37,217,208,0.75)", "rgba(198,243,168,0.25)"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.scoreBorder}
          >
            <View style={styles.scoreInner}>
              <Text style={styles.bannerText}>
                You meet about {readinessScore}% of requirements
              </Text>

              <View style={styles.ring}>
                <Svg width={RING} height={RING} style={{ transform: [{ rotate: "-90deg" }] }}>
                  <Defs>
                    <SvgGradient id="ring" x1="0" y1="0" x2="1" y2="1">
                      <Stop offset="0" stopColor={brand.cyan} />
                      <Stop offset="1" stopColor={brand.mint} />
                    </SvgGradient>
                  </Defs>
                  <Circle
                    cx={RING / 2}
                    cy={RING / 2}
                    r={RADIUS}
                    stroke="rgba(255,255,255,0.08)"
                    strokeWidth={STROKE}
                    fill="none"
                  />
                  <Circle
                    cx={RING / 2}
                    cy={RING / 2}
                    r={RADIUS}
                    stroke="url(#ring)"
                    strokeWidth={STROKE}
                    strokeLinecap="round"
                    strokeDasharray={CIRC}
                    strokeDashoffset={CIRC * (1 - readinessScore / 100)}
                    fill="none"
                  />
                </Svg>
                <Text style={styles.scoreText}>{readinessScore}%</Text>
              </View>

              <Text style={styles.scoreTitle}>Career readiness index</Text>
            </View>
          </LinearGradient>

          <Text style={styles.sectionTitle}>Identified gaps</Text>

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

                  <Text style={styles.scoreLabel}>{item.score}% proficiency</Text>
                </View>
              );
            })}
          </View>

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

  screenTitle: {
    fontFamily: SERIF,
    fontSize: 32,
    lineHeight: 37,
    fontWeight: "400",
    letterSpacing: -0.5,
    color: brand.text,
    marginTop: 16,
    marginBottom: 24,
  },

  scoreBorder: { borderRadius: 20, padding: 1, marginBottom: 32 },
  scoreInner: {
    backgroundColor: brand.surfaceSolid,
    borderRadius: 19,
    padding: 24,
    alignItems: "center",
  },
  bannerText: { fontSize: 14, color: brand.muted, marginBottom: 24, textAlign: "center" },
  ring: { width: RING, height: RING, alignItems: "center", justifyContent: "center", marginBottom: 16 },
  scoreText: { position: "absolute", fontSize: 30, fontWeight: "700", color: brand.text },
  scoreTitle: { fontSize: 16, fontWeight: "600", color: brand.text },

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

  track: { height: 6, borderRadius: 3, backgroundColor: "rgba(255,255,255,0.08)", overflow: "hidden" },
  fill: { height: 6, borderRadius: 3 },
  scoreLabel: { fontSize: 13, color: brand.muted, marginTop: 8 },

  buttonWrap: { marginTop: 28, borderRadius: 999, overflow: "hidden" },
  button: { height: 50, alignItems: "center", justifyContent: "center" },
  buttonText: { color: brand.onGradient, fontSize: 15, fontWeight: "700" },

  emptyContainer: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 32 },
  emptyIconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "rgba(37,217,208,0.12)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },
  emptyTitle: { fontFamily: SERIF, fontSize: 24, color: brand.text, textAlign: "center", marginBottom: 10 },
  emptyMessage: { fontSize: 14, lineHeight: 20, color: brand.muted, textAlign: "center", marginBottom: 8 },
});