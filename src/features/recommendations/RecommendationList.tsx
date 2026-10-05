import { Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { brand } from "@/components/ui/brand";
import { useAppData } from "@/state/appdatacontext";

export type Recommendation = {
  id: string;
  title: string;
  provider: string;
  duration: string;
  skill: string; // the gap this closes
  match: number; // 0-100, how well it fits the gap
};

// TODO: replace with a real Recommendation Engine query (ranked learning
// resources per skill gap). For now, derives one mock course per identified
// gap so the list at least reflects the user's actual analysis instead of
// always showing the same three unrelated sample courses.
function buildMockRecommendations(gapSkills: string[]): Recommendation[] {
  const PROVIDERS = ["Coursera", "edX", "Udemy"];
  return gapSkills.map((skill, i) => ({
    id: String(i + 1),
    skill,
    title: `${skill} fundamentals`,
    provider: PROVIDERS[i % PROVIDERS.length],
    duration: `${3 + i} hours`,
    match: Math.max(50, 90 - i * 8),
  }));
}

type Props = {
  items?: Recommendation[];
  onPressItem?: (item: Recommendation) => void;
};

export function RecommendationList({ items, onPressItem }: Props) {
  const router = useRouter();
  const { analysis } = useAppData();

  const resolvedItems =
    items ?? (analysis ? buildMockRecommendations(analysis.gaps.map((g) => g.skill)) : []);

  if (resolvedItems.length === 0) {
    return (
      <View style={styles.empty}>
        <View style={styles.emptyIconCircle}>
          <Feather name="book-open" size={24} color={brand.cyan} />
        </View>
        <Text style={styles.emptyTitle}>No recommendations yet</Text>
        <Text style={styles.emptyText}>
          Analyze your resume to get recommendations tailored to your skill gaps.
        </Text>
        <Pressable
          onPress={() => router.push("/resume-upload")}
          style={({ pressed }) => [styles.emptyButtonWrap, pressed && { opacity: 0.85 }]}
        >
          <LinearGradient
            colors={[brand.cyan, brand.mint]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.emptyButton}
          >
            <Text style={styles.emptyButtonText}>Upload your resume</Text>
          </LinearGradient>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.list}>
      {resolvedItems.map((item) => (
        <Pressable
          key={item.id}
          onPress={() => onPressItem?.(item)}
          accessibilityRole="button"
          style={({ pressed }) => [styles.card, pressed && { opacity: 0.85 }]}
        >
          <View style={styles.topRow}>
            <View style={styles.pill}>
              <Text style={styles.pillText}>{item.skill}</Text>
            </View>
            <Feather name="arrow-up-right" size={18} color={brand.muted} />
          </View>

          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.meta}>
            {item.provider}, {item.duration}
          </Text>

          <View style={styles.matchRow}>
            <View style={styles.track}>
              <LinearGradient
                colors={[brand.cyan, brand.mint]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={[styles.fill, { width: `${item.match}%` }]}
              />
            </View>
            <Text style={styles.matchText}>{item.match}% match</Text>
          </View>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: 12 },
  card: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 18,
  },
  topRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  pill: { backgroundColor: brand.tint, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  pillText: { fontSize: 13, fontWeight: "600", color: brand.cyan },
  title: { fontSize: 18, fontWeight: "700", color: brand.text, marginBottom: 4 },
  meta: { fontSize: 14, color: brand.muted, marginBottom: 16 },
  matchRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  track: { flex: 1, height: 4, borderRadius: 2, backgroundColor: "rgba(255,255,255,0.08)", overflow: "hidden" },
  fill: { height: 4, borderRadius: 2 },
  matchText: { fontSize: 13, fontWeight: "600", color: brand.text },
  empty: { alignItems: "center", paddingVertical: 48, paddingHorizontal: 16 },
  emptyIconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "rgba(37,217,208,0.12)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: brand.text, marginBottom: 6 },
  emptyText: { fontSize: 14, color: brand.muted, textAlign: "center", marginBottom: 20, lineHeight: 20 },
  emptyButtonWrap: { borderRadius: 999, overflow: "hidden" },
  emptyButton: { paddingVertical: 12, paddingHorizontal: 24, alignItems: "center" },
  emptyButtonText: { color: brand.onGradient, fontWeight: "700", fontSize: 14 },
});