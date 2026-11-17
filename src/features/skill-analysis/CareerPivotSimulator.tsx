import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import type { Analysis } from "@/state/appdatacontext";
import { brand } from "@/components/ui/theme";
import { getCareerPivotRoles, type CareerPivotRole } from "@/services/skillAnalysisService";

const SKILL_ALIASES: Record<string, string[]> = {
  "front end development": ["frontend development", "web development"],
  "back end development": ["backend development", "server side development"],
  "api development": ["api design", "web services"],
  "user research": ["user experience research", "market research"],
  "stakeholder management": ["stakeholder engagement", "stakeholder communication"],
  "project management": ["manage projects", "project coordination"],
  "roadmapping": ["product roadmap", "product planning"],
  "product strategy": ["product management", "product planning"],
  "data analysis": ["data analytics", "analyse data", "analyze data"],
  "javascript": ["javascript programming", "js"],
  "react": ["react.js", "reactjs"],
  "testing": ["software testing", "test software"],
  "cloud computing": ["cloud services", "cloud platforms"],
  "communication": ["communicate", "interpersonal communication"],
  "ui design": ["user interface design", "interface design"],
};

function normalizeSkill(skill: string) {
  return skill.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function skillMatches(left: string, right: string) {
  const leftKey = normalizeSkill(left);
  const rightKey = normalizeSkill(right);
  if (leftKey === rightKey) return true;
  const leftAliases = [leftKey, ...(SKILL_ALIASES[leftKey] ?? []).map(normalizeSkill)];
  const rightAliases = [rightKey, ...(SKILL_ALIASES[rightKey] ?? []).map(normalizeSkill)];
  return leftAliases.some((alias) => rightAliases.includes(alias));
}

export function CareerPivotSimulator({ analysis }: { analysis: Analysis }) {
  const [careerPaths, setCareerPaths] = useState<CareerPivotRole[]>([]);
  const [pathsLoading, setPathsLoading] = useState(true);
  const [pathsError, setPathsError] = useState<string | null>(null);
  const [reloadPaths, setReloadPaths] = useState(0);
  const [selectedPathName, setSelectedPathName] = useState("");

  useEffect(() => {
    let active = true;
    setPathsLoading(true);
    setPathsError(null);
    getCareerPivotRoles().then((paths) => {
      if (active) setCareerPaths(paths);
    }).catch((error: unknown) => {
      if (!active) return;
      console.error("Could not load career pivot paths:", error);
      setPathsError(error instanceof Error ? error.message : "Could not load career paths.");
    }).finally(() => {
      if (active) setPathsLoading(false);
    });
    return () => { active = false; };
  }, [reloadPaths]);

  const baseline = useMemo(() => {
    if (analysis.extractedSkills !== undefined) {
      return analysis.extractedSkills.map((item) => ({
        skill: item.skill,
        uri: item.uri,
        credit: 1,
      }));
    }

    // Older saved analyses did not retain the pre-gap extracted skill inventory.
    const inventory = analysis.requirements.map((item) => ({
      skill: item.skill,
      uri: item.uri,
      credit: item.credit,
    }));
    for (const skill of analysis.covered) {
      if (!inventory.some((item) => skillMatches(item.skill, skill))) {
        inventory.push({
          skill,
          uri: `covered:${normalizeSkill(skill)}`,
          credit: 1,
        });
      }
    }
    return inventory;
  }, [analysis.covered, analysis.extractedSkills, analysis.requirements]);

  const comparisons = useMemo(() => careerPaths.map((path) => {
    const skills = path.requirements.map((requirement) => {
      const evidence = baseline.find((item) =>
        item.uri === requirement.uri || skillMatches(item.skill, requirement.skill),
      );
      return {
        skill: requirement.skill,
        credit: evidence ? Math.max(0, Math.min(1, evidence.credit)) : 0,
      };
    });
    const score = skills.length
      ? skills.reduce((total, skill) => total + skill.credit, 0) / skills.length
      : 0;
    return { path, skills, score };
  }), [baseline, careerPaths]);

  const topPivots = useMemo(() => comparisons
    .filter((comparison) =>
      comparison.skills.length > 0
      && comparison.path.role.toLowerCase() !== analysis.targetRole.toLowerCase(),
    )
    .sort((a, b) => b.score - a.score || a.path.role.localeCompare(b.path.role))
    .slice(0, 3), [analysis.targetRole, comparisons]);

  useEffect(() => {
    if (!topPivots.length) return;
    setSelectedPathName((current) =>
      topPivots.some((comparison) => comparison.path.role === current)
        ? current
        : topPivots[0].path.role,
    );
  }, [topPivots]);

  const selected = topPivots.find((comparison) => comparison.path.role === selectedPathName);
  const bestFit = topPivots[0];
  const matchedCount = selected?.skills.filter((skill) => skill.credit > 0).length ?? 0;
  const gapCount = (selected?.skills.length ?? 0) - matchedCount;

  if (!baseline.length) {
    return (
      <View style={styles.emptyCard}>
        <Feather name="info" size={20} color={brand.cyan} />
        <Text style={styles.emptyTitle}>No skill inventory to compare yet</Text>
        <Text style={styles.description}>
          Run a resume analysis with detailed skill results before exploring career paths.
        </Text>
      </View>
    );
  }

  if (pathsLoading) {
    return (
      <View style={styles.emptyCard}>
        <Text style={styles.description}>Loading available roles and their requirements…</Text>
      </View>
    );
  }

  if (pathsError) {
    return (
      <View style={styles.emptyCard}>
        <Feather name="alert-circle" size={20} color={brand.cyan} />
        <Text style={styles.emptyTitle}>Could not load available roles</Text>
        <Text style={styles.description}>{pathsError}</Text>
        <Pressable style={styles.retryButton} onPress={() => setReloadPaths((count) => count + 1)}>
          <Text style={styles.retryButtonText}>Try again</Text>
        </Pressable>
      </View>
    );
  }

  if (!topPivots.length) {
    return (
      <View style={styles.emptyCard}>
        <Feather name="info" size={20} color={brand.cyan} />
        <Text style={styles.emptyTitle}>No alternative role requirements available</Text>
        <Text style={styles.description}>
          The backend has no other supported roles with requirements to compare against your current role.
        </Text>
      </View>
    );
  }

  if (!selected || !bestFit) return null;

  return (
    <View style={styles.container}>
      <View style={styles.introCard}>
        <View style={styles.introHeading}>
          <View style={styles.iconCircle}>
            <Feather name="shuffle" size={18} color={brand.cyan} />
          </View>
          <Text style={styles.title}>Career Pivot Simulator</Text>
        </View>
        <Text style={styles.description}>
          Top three alternative roles by overlap with your extracted resume skills. Switch between them to see transferable skills and gaps.
        </Text>
        {analysis.demo && (
          <Text style={styles.demoNote}>Demo skills are sample data, so these comparisons are illustrative.</Text>
        )}
      </View>

      <View style={styles.pathOptions}>
        {topPivots.map((comparison) => {
          const { path } = comparison;
          const selectedPath = selectedPathName === path.role;
          return (
            <Pressable
              key={path.role}
              onPress={() => setSelectedPathName(path.role)}
              accessibilityRole="button"
              accessibilityState={{ selected: selectedPath }}
              style={[styles.pathOption, selectedPath && styles.pathOptionSelected]}
            >
              <View style={styles.pathOptionHeading}>
                <Feather name="briefcase" size={17} color={selectedPath ? brand.cyan : brand.muted} />
                <Text style={[styles.pathTitle, selectedPath && styles.pathTitleSelected]}>{path.role}</Text>
              </View>
              <Text style={styles.pathScore}>
                {Math.round(comparison.score * 100)}% overlap · {comparison.skills.length} requirements
              </Text>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.resultCard}>
        <Text style={styles.resultEyebrow}>PATH SNAPSHOT</Text>
        <Text style={styles.resultTitle}>{selected.path.role}</Text>
        <View style={styles.scoreRow}>
          <Text style={styles.scoreValue}>{Math.round(selected.score * 100)}%</Text>
          <Text style={styles.scoreCaption}>estimated skill overlap</Text>
        </View>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${Math.round(selected.score * 100)}%` }]} />
        </View>
        <Text style={styles.fitNote}>
          {selected.path.role === bestFit.path.role
            ? "This is the alternative role with the highest overlap."
            : `${bestFit.path.role} has the highest overlap at ${Math.round(bestFit.score * 100)}%.`}
        </Text>

        <View style={styles.summaryRow}>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryValue}>{matchedCount}</Text>
            <Text style={styles.summaryLabel}>transferable skills</Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryItem}>
            <Text style={styles.gapValue}>{gapCount}</Text>
            <Text style={styles.summaryLabel}>skills to develop</Text>
          </View>
        </View>

        <Text style={styles.listHeading}>Your skill inventory</Text>
        <View style={styles.skillList}>
          {selected.skills.map(({ skill, credit }) => {
            const matched = credit > 0;
            return (
              <View key={skill} style={styles.skillRow}>
                <Feather
                  name={matched ? "check-circle" : "circle"}
                  size={16}
                  color={matched ? brand.cyan : "#E8A1A1"}
                />
                <Text style={styles.skillName}>{skill}</Text>
                <Text style={[styles.skillStatus, matched ? styles.transferable : styles.toLearn]}>
                  {matched ? "Transferable" : "To develop"}
                </Text>
              </View>
            );
          })}
        </View>
      </View>

      <Text style={styles.disclaimer}>
        Skills are matched against the backend&apos;s current role profiles. This overlap estimate is not a full resume re-analysis for the selected role.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 14, marginBottom: 28 },
  introCard: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 16,
  },
  introHeading: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 10 },
  iconCircle: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: brand.tint,
    alignItems: "center",
    justifyContent: "center",
  },
  title: { color: brand.text, fontSize: 18, fontWeight: "700" },
  description: { color: brand.muted, fontSize: 13, lineHeight: 19 },
  demoNote: { color: "#B45309", fontSize: 12, lineHeight: 17, marginTop: 8 },
  retryButton: {
    backgroundColor: brand.tint,
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 9,
  },
  retryButtonText: { color: brand.cyan, fontSize: 13, fontWeight: "700" },
  pathOptions: { gap: 8 },
  pathOption: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 12,
    padding: 13,
  },
  pathOptionSelected: { borderColor: brand.cyan, backgroundColor: brand.tint },
  pathOptionHeading: { flexDirection: "row", alignItems: "center", gap: 9 },
  pathTitle: { color: brand.text, fontSize: 14, fontWeight: "700" },
  pathTitleSelected: { color: brand.cyan },
  pathScore: { color: brand.muted, fontSize: 12, marginTop: 5, marginLeft: 26 },
  resultCard: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 16,
  },
  resultEyebrow: { color: brand.cyan, fontSize: 10, fontWeight: "800", letterSpacing: 1.2 },
  resultTitle: { color: brand.text, fontSize: 20, fontWeight: "700", marginTop: 4 },
  scoreRow: { flexDirection: "row", alignItems: "baseline", gap: 8, marginTop: 12 },
  scoreValue: { color: brand.text, fontSize: 30, fontWeight: "800" },
  scoreCaption: { color: brand.muted, fontSize: 13 },
  progressTrack: { height: 7, borderRadius: 99, backgroundColor: brand.border, overflow: "hidden", marginTop: 7 },
  progressFill: { height: "100%", borderRadius: 99, backgroundColor: brand.cyan },
  fitNote: { color: brand.muted, fontSize: 12, lineHeight: 18, marginTop: 9 },
  summaryRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: brand.bg,
    borderRadius: 12,
    paddingVertical: 12,
    marginTop: 15,
  },
  summaryItem: { flex: 1, alignItems: "center", gap: 3 },
  summaryValue: { color: brand.cyan, fontSize: 19, fontWeight: "800" },
  gapValue: { color: "#E8A1A1", fontSize: 19, fontWeight: "800" },
  summaryLabel: { color: brand.muted, fontSize: 11 },
  summaryDivider: { width: 1, height: 30, backgroundColor: brand.border },
  listHeading: { color: brand.text, fontSize: 14, fontWeight: "700", marginTop: 18, marginBottom: 8 },
  skillList: { gap: 3 },
  skillRow: { minHeight: 38, flexDirection: "row", alignItems: "center", gap: 9 },
  skillName: { flex: 1, color: brand.text, fontSize: 13 },
  skillStatus: { fontSize: 11, fontWeight: "600" },
  transferable: { color: brand.cyan },
  toLearn: { color: "#E8A1A1" },
  disclaimer: { color: brand.muted, fontSize: 11, lineHeight: 16, paddingHorizontal: 2 },
  emptyCard: {
    alignItems: "center",
    gap: 10,
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 20,
    marginBottom: 28,
  },
  emptyTitle: { color: brand.text, fontSize: 16, fontWeight: "700", textAlign: "center" },
});
