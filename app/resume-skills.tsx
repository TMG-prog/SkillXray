import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { getResumeSkillNames } from "@/services/skillAnalysisService";
import { brand, SERIF } from "@/components/ui/brand";

const AMBER = "#F2C879";

export default function ResumeSkillsScreen() {
  const router = useRouter();
  const { resumeId, fileName } = useLocalSearchParams<{ resumeId: string; fileName?: string }>();
  const [skills, setSkills] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!resumeId) {
      setError("No resume selected.");
      return;
    }
    let cancelled = false;
    getResumeSkillNames(resumeId)
      .then((list) => !cancelled && setSkills(list))
      .catch((e) => !cancelled && setError(e?.message ?? "Could not load your skills."));
    return () => {
      cancelled = true;
    };
  }, [resumeId]);

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <Text style={styles.title}>Skills extracted from your resume</Text>
      {fileName ? <Text style={styles.subtitle}>{fileName}</Text> : null}

      <View style={styles.card}>
        {error ? (
          <Text style={styles.error}>{error}</Text>
        ) : skills === null ? (
          <ActivityIndicator color={brand.cyan} />
        ) : skills.length === 0 ? (
          <Text style={styles.muted}>No skills were found in this resume.</Text>
        ) : (
          <>
            <Text style={styles.count}>
              {skills.length} {skills.length === 1 ? "skill" : "skills"} found
            </Text>
            <View style={styles.chips}>
              {skills.map((skill) => (
                <View key={skill} style={styles.chip}>
                  <Text style={styles.chipText}>{skill}</Text>
                </View>
              ))}
            </View>
          </>
        )}
      </View>

      {/* Placeholder until the skill gap analyzer is built. */}
      <View style={styles.card}>
        <StatusRow icon="check-circle" color={brand.mint} text="Skills passed to the skill gap analyzer" />
        <View style={styles.divider} />
        <StatusRow icon="clock" color={AMBER} text="Skill gap analyzer not ready" />
        <Text style={styles.note}>Your skill gap results will appear here once the analyzer is available.</Text>
      </View>

      <Pressable
        onPress={() => router.replace("/(tabs)")}
        accessibilityRole="button"
        style={({ pressed }) => [styles.buttonWrap, pressed && { opacity: 0.85 }]}
      >
        <LinearGradient
          colors={[brand.cyan, brand.mint]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.button}
        >
          <Text style={styles.buttonText}>Back to home</Text>
        </LinearGradient>
      </Pressable>

      <Pressable onPress={() => router.replace("/resume-upload")} accessibilityRole="button" style={styles.link}>
        <Text style={styles.linkText}>Upload a different resume</Text>
      </Pressable>
    </ScrollView>
  );
}

function StatusRow({ icon, color, text }: { icon: "check-circle" | "clock"; color: string; text: string }) {
  return (
    <View style={styles.statusRow}>
      <Feather name={icon} size={20} color={color} />
      <Text style={styles.statusText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: brand.bg },
  container: { padding: 20, paddingBottom: 40 },
  title: { fontFamily: SERIF, fontSize: 28, lineHeight: 33, color: brand.text, letterSpacing: -0.4 },
  subtitle: { fontSize: 14, color: brand.muted, marginTop: 6 },

  card: {
    marginTop: 20,
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 18,
  },
  count: { fontSize: 14, fontWeight: "600", color: brand.muted, marginBottom: 12 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    backgroundColor: brand.tint,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  chipText: { fontSize: 14, fontWeight: "600", color: brand.cyan },
  muted: { fontSize: 14, color: brand.muted },
  error: { fontSize: 14, color: "#FF8F86" },

  statusRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  statusText: { flex: 1, fontSize: 15, fontWeight: "600", color: brand.text },
  divider: { height: 1, backgroundColor: brand.border, marginVertical: 14 },
  note: { fontSize: 13, lineHeight: 19, color: brand.muted, marginTop: 12 },

  buttonWrap: { marginTop: 24, borderRadius: 999, overflow: "hidden" },
  button: { height: 50, alignItems: "center", justifyContent: "center" },
  buttonText: { color: brand.onGradient, fontSize: 16, fontWeight: "700" },
  link: { alignItems: "center", paddingVertical: 16 },
  linkText: { fontSize: 14, fontWeight: "600", color: brand.cyan },
});