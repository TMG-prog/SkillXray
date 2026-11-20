import { Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { brand, SERIF } from "@/components/ui/theme";
import { useAppData } from "@/state/appdatacontext";

export type Recommendation = {
  id: string;
  title: string;
  provider: string;
  url: string;
  skill: string; // the gap this closes
  rank?: number;
  marginalGainPoints?: number;
  clusterGainPoints?: number;
  prerequisites?: string[];
  clusterSkills?: string[];
  coveredBy?: string | null;
  hiringEvidence?: string;
};

function buildRecommendations(gapSkills: string[]): Recommendation[] {
  return gapSkills.map((skill, index) => ({
    id: `course-search-${index}-${skill}`,
    title: `Find courses for ${skill}`,
    provider: "Coursera course search",
    url: `https://www.coursera.org/search?query=${encodeURIComponent(skill)}`,
    skill,
    rank: index + 1,
  }));
}

async function openCourse(url: string) {
  try {
    await Linking.openURL(url);
  } catch (error) {
    console.error("[recommendations] unable to open course page", error);
    Alert.alert("Couldn't open course", "Please try again or open the course link in your browser.");
  }
}

type Props = {
  items?: Recommendation[];
  onPressItem?: (item: Recommendation) => void;
  roadmap?: boolean;
};

export function RecommendationList({ items, onPressItem, roadmap = false }: Props) {
  const router = useRouter();
  const { analysis } = useAppData();

  const resolvedItems =
    items ?? (analysis?.learningPlan?.length
      ? analysis.learningPlan.map((step) => ({
        id: step.uri,
        title: step.resource.title,
        provider: step.resource.provider,
        url: step.resource.url,
        skill: step.skill,
        rank: step.rank,
        marginalGainPoints: step.marginalGainPoints,
        clusterGainPoints: step.clusterGainPoints,
        prerequisites: roadmap
          ? step.prerequisites.filter((skill) => analysis.relationships.some((relationship) =>
            relationship.type === "prerequisite"
            && relationship.source === skill
            && relationship.target === step.skill))
          : step.prerequisites,
        clusterSkills: step.clusterSkills,
        coveredBy: step.coveredBy,
        hiringEvidence: step.hiringEvidence?.evidence,
      }))
      : analysis && !roadmap ? buildRecommendations(analysis.gaps.map((g) => g.skill)) : []);

  if (resolvedItems.length === 0) {
    if (roadmap && analysis) {
      return (
        <View style={styles.roadmapSection}>
          <Text style={styles.roadmapTitle}>Your learning roadmap</Text>
          <Text style={styles.roadmapDescription}>
            {analysis.gaps.length || !analysis.requirements.length
              ? "No learning plan is available for this analysis. Run a new analysis to generate one."
              : "No uncovered skills were identified for this role."}
          </Text>
        </View>
      );
    }
    return (
      <View style={styles.empty}>
        <View style={styles.emptyIconCircle}>
          <Feather name="book-open" size={24} color={brand.cyan} />
        </View>
        <Text style={styles.emptyTitle}>
          {analysis ? "No course links available yet" : "No recommendations yet"}
        </Text>
        <Text style={styles.emptyText}>
          {analysis
            ? "We don't have a curated enrollment link for these skill gaps yet."
            : "Analyze your resume to get recommendations tailored to your skill gaps."}
        </Text>
        {!analysis && (
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
        )}
      </View>
    );
  }

  return (
    <View style={[styles.list, roadmap && styles.roadmapSection]}>
      {roadmap && (
        <View>
          <Text style={styles.roadmapTitle}>Your learning roadmap</Text>
          <Text style={styles.roadmapDescription}>
            Suggested steps based on your skill gaps and estimated impact. Gains are estimates, assuming earlier steps are learned, not guaranteed score changes.
          </Text>
        </View>
      )}
      {resolvedItems.map((item, index) => (
        <Pressable
          key={item.id}
          onPress={() => onPressItem ? onPressItem(item) : openCourse(item.url)}
          accessibilityRole="button"
          accessibilityLabel={`${item.title}. View learning resource.`}
          style={({ pressed }) => [styles.card, pressed && { opacity: 0.85 }]}
        >
          {roadmap && index === 0 && <Text style={styles.startHere}>START HERE</Text>}
          <View style={styles.topRow}>
            <View style={styles.pillRow}>
              {item.rank !== undefined && (
                <View style={styles.pill}>
                  <Text style={styles.pillText}>Step {item.rank}</Text>
                </View>
              )}
              <View style={styles.pill}>
                <Text style={styles.pillText}>{item.skill}</Text>
              </View>
            </View>
            <Feather name="arrow-up-right" size={18} color={brand.muted} />
          </View>

          {roadmap && <Text style={styles.roadmapSkill}>{item.skill}</Text>}
          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.meta}>{item.provider}</Text>
          {item.marginalGainPoints !== undefined && (
            <Text style={styles.evidence}>
              {roadmap ? "Estimated readiness gain" : "Up to"} +{item.marginalGainPoints.toFixed(1)} {roadmap ? "points" : "CRI points when learned"}.
            </Text>
          )}
          {item.clusterGainPoints !== undefined
            && item.marginalGainPoints !== undefined
            && item.clusterGainPoints > item.marginalGainPoints && (
              <Text style={styles.evidence}>
                Related-skill cluster: up to +{item.clusterGainPoints.toFixed(1)} CRI points across the listed cluster.
              </Text>
            )}
          {item.prerequisites && item.prerequisites.length > 0 && (
            <Text style={styles.evidence}>
              {roadmap ? "Prerequisites: " : "Learn after: "}
              {item.prerequisites.map((skill) => roadmap && analysis?.covered.includes(skill)
                ? `${skill} (matched in CV)` : skill).join(", ")}
            </Text>
          )}
          {item.clusterSkills && item.clusterSkills.length > 0 && (
            <Text style={styles.evidence}>Related skill cluster: {item.clusterSkills.join(", ")}</Text>
          )}
          {item.coveredBy && (
            <Text style={styles.evidence}>This requirement is also addressed by learning {item.coveredBy}.</Text>
          )}
          {item.hiringEvidence && (
            <Text style={styles.evidence}>Hiring evidence: {item.hiringEvidence}</Text>
          )}

          <View style={styles.courseLink}>
            <Text style={styles.courseLinkText}>{roadmap ? "View learning resource" : "View course & enroll"}</Text>
            <Feather name="external-link" size={15} color={brand.cyan} />
          </View>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: 12 },
  roadmapSection: { marginBottom: 24 },
  roadmapTitle: { color: brand.text, fontSize: 18, fontWeight: "700", marginBottom: 6 },
  roadmapDescription: { color: brand.muted, fontSize: 13, lineHeight: 19 },
  startHere: { color: brand.cyan, fontSize: 11, fontWeight: "700", marginBottom: 10 },
  roadmapSkill: { color: brand.text, fontSize: 17, fontWeight: "700", marginBottom: 6 },
  card: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 18,
  },
  topRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  pillRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  pill: { backgroundColor: brand.tint, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  pillText: { fontSize: 13, fontWeight: "600", color: brand.cyan },
  title: { fontSize: 18, fontWeight: "700", color: brand.text, marginBottom: 4 },
  meta: { fontSize: 14, color: brand.muted, marginBottom: 16 },
  evidence: { fontSize: 12, lineHeight: 17, color: brand.muted, marginTop: 4 },
  courseLink: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 16 },
  courseLinkText: { fontSize: 14, fontWeight: "700", color: brand.cyan },
  empty: { alignItems: "center", paddingVertical: 48, paddingHorizontal: 16 },
  emptyIconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: brand.tint,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  emptyTitle: { fontFamily: SERIF, fontSize: 20, color: brand.text, marginBottom: 6 },
  emptyText: { fontSize: 14, color: brand.muted, textAlign: "center", marginBottom: 20, lineHeight: 20 },
  emptyButtonWrap: { borderRadius: 999, overflow: "hidden" },
  emptyButton: { paddingVertical: 12, paddingHorizontal: 24, alignItems: "center" },
  emptyButtonText: { color: brand.onGradient, fontWeight: "700", fontSize: 14 },
});