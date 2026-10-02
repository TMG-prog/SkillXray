import { Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import { brand } from "@/components/ui/brand";

export type Recommendation = {
  id: string;
  title: string;
  provider: string;
  duration: string;
  skill: string; // the gap this closes
  match: number; // 0-100, how well it fits the gap
};

// Placeholder data: replace with your real recommendations (props or a Supabase query).
const SAMPLE: Recommendation[] = [
  { id: "1", title: "SQL for Data Analysis", provider: "Coursera", duration: "6 hours", skill: "SQL", match: 94 },
  { id: "2", title: "Intro to Machine Learning", provider: "Kaggle", duration: "4 hours", skill: "Machine learning", match: 82 },
  { id: "3", title: "Data Storytelling", provider: "LinkedIn Learning", duration: "3 hours", skill: "Communication", match: 71 },
];

type Props = {
  items?: Recommendation[];
  onPressItem?: (item: Recommendation) => void;
};

export function RecommendationList({ items = SAMPLE, onPressItem }: Props) {
  if (items.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>No recommendations yet</Text>
        <Text style={styles.emptyText}>Analyze your resume to get recommendations.</Text>
      </View>
    );
  }

  return (
    <View style={styles.list}>
      {items.map((item) => (
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
  empty: { alignItems: "center", paddingVertical: 48 },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: brand.text, marginBottom: 6 },
  emptyText: { fontSize: 14, color: brand.muted, textAlign: "center" },
});
