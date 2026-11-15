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
};

const COURSES = [
  {
    id: "python-for-everybody",
    title: "Python for Everybody Specialization",
    provider: "Coursera · University of Michigan",
    url: "https://www.coursera.org/specializations/python",
    matches: ["python"],
  },
  {
    id: "sql-for-data-science",
    title: "SQL for Data Science",
    provider: "Coursera · University of California, Davis",
    url: "https://www.coursera.org/learn/sql-for-data-science",
    matches: ["sql", "database"],
  },
  {
    id: "google-data-analytics",
    title: "Google Data Analytics Professional Certificate",
    provider: "Coursera · Google",
    url: "https://www.coursera.org/professional-certificates/google-data-analytics",
    matches: ["data analytics", "data analyst", "statistics", "power bi", "tableau", "spreadsheets", "business intelligence"],
  },
  {
    id: "machine-learning-specialization",
    title: "Machine Learning Specialization",
    provider: "Coursera · DeepLearning.AI and Stanford",
    url: "https://www.coursera.org/specializations/machine-learning-introduction",
    matches: ["machine learning", "artificial intelligence", "data science", "computer vision", "deep learning"],
  },
  {
    id: "google-project-management",
    title: "Google Project Management Professional Certificate",
    provider: "Coursera · Google",
    url: "https://www.coursera.org/professional-certificates/google-project-management",
    matches: ["project management", "project manager", "project commissioning"],
  },
  {
    id: "google-it-support",
    title: "Google IT Support Professional Certificate",
    provider: "Coursera · Google",
    url: "https://www.coursera.org/professional-certificates/google-it-support",
    matches: ["it support", "troubleshoot", "operating systems", "computer technology", "technical support"],
  },
  {
    id: "java-programming",
    title: "Java Programming and Software Engineering Fundamentals",
    provider: "Coursera · Duke University",
    url: "https://www.coursera.org/specializations/java-programming",
    matches: ["java"],
  },
];

function buildRecommendations(gapSkills: string[]): Recommendation[] {
  const recommendations = new Map<string, Recommendation>();

  for (const skill of gapSkills) {
    const normalized = skill.toLowerCase();
    const course = COURSES.find(({ matches }) =>
      matches.some((match) => normalized.includes(match)),
    );
    if (!course || recommendations.has(course.id)) continue;

    recommendations.set(course.id, {
      id: course.id,
      title: course.title,
      provider: course.provider,
      url: course.url,
      skill,
    });
  }

  return [...recommendations.values()];
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
};

export function RecommendationList({ items, onPressItem }: Props) {
  const router = useRouter();
  const { analysis } = useAppData();

  const resolvedItems =
    items ?? (analysis ? buildRecommendations(analysis.gaps.map((g) => g.skill)) : []);

  if (resolvedItems.length === 0) {
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
    <View style={styles.list}>
      {resolvedItems.map((item) => (
        <Pressable
          key={item.id}
          onPress={() => onPressItem ? onPressItem(item) : openCourse(item.url)}
          accessibilityRole="button"
          accessibilityLabel={`${item.title}. View course and enroll.`}
          style={({ pressed }) => [styles.card, pressed && { opacity: 0.85 }]}
        >
          <View style={styles.topRow}>
            <View style={styles.pill}>
              <Text style={styles.pillText}>{item.skill}</Text>
            </View>
            <Feather name="arrow-up-right" size={18} color={brand.muted} />
          </View>

          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.meta}>{item.provider}</Text>

          <View style={styles.courseLink}>
            <Text style={styles.courseLinkText}>View course & enroll</Text>
            <Feather name="external-link" size={15} color={brand.cyan} />
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