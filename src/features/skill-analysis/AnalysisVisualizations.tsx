import { StyleSheet, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";
import type {
  AnalysisMarketInsights,
  AnalysisRequirement,
  AnalysisSkillRelationship,
} from "@/state/appdatacontext";
import { brand } from "@/components/ui/theme";

export function AnalysisVisualizations({
  requirements,
  relationships,
  covered,
  marketInsights,
  view,
}: {
  requirements: AnalysisRequirement[];
  relationships: AnalysisSkillRelationship[];
  covered: string[];
  marketInsights: AnalysisMarketInsights;
  view: "skills" | "market" | "pathways";
}) {
  const topSkills = [...requirements]
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 6);
  const demandSkills = requirements.filter((skill) => skill.frequency !== null);
  const demandMaximum = Math.max(0, ...demandSkills.map((skill) => skill.frequency ?? 0));
  const emergingSkills = marketInsights.emergingSkills ?? [];
  const currentPostings = marketInsights.currentPostings ?? 0;
  const previousPostings = marketInsights.previousPostings ?? 0;
  const heatmap = Array.from({ length: 9 }, () => [] as AnalysisRequirement[]);

  for (const skill of demandSkills) {
    const demandRatio = demandMaximum > 0 ? (skill.frequency ?? 0) / demandMaximum : 0;
    const demandBand = demandRatio >= 0.67 ? 2 : demandRatio >= 0.34 ? 1 : 0;
    const gapBand = skill.credit >= 0.67 ? 0 : skill.credit >= 0.34 ? 1 : 2;
    heatmap[(2 - gapBand) * 3 + demandBand].push(skill);
  }

  return (
    <View style={styles.container}>
      {view === "skills" && <View style={styles.card}>
        <Text style={styles.title}>Current vs. target skills</Text>
        <Text style={styles.description}>
          Your match credit, remaining gap, role weight, and posting demand for the role&apos;s most important skills.
        </Text>
        {topSkills.length ? (
          <>
            <View style={styles.radarTable}>
              <View style={styles.radarTableHeader}>
                <Text style={[styles.radarColumnHeader, styles.radarSkillColumn]}>SKILL</Text>
                <Text style={styles.radarColumnHeader}>MATCH</Text>
                <Text style={styles.radarColumnHeader}>GAP</Text>
                <Text style={[styles.radarColumnHeader, styles.radarDemandColumn]}>DEMAND</Text>
              </View>
              {topSkills.map((skill) => (
                <View key={skill.uri} style={styles.radarSkillRow}>
                  <View style={styles.radarSkillColumn}>
                    <Text style={styles.radarSkillName}>{skill.skill}</Text>
                    <Text style={styles.radarSkillMeta}>
                      Target 100% · Role weight {Math.round(skill.weight * 100)}%
                    </Text>
                  </View>
                  <Text style={[styles.radarValue, styles.radarCurrentValue]}>
                    {Math.round(skill.credit * 100)}%
                  </Text>
                  <Text style={[styles.radarValue, styles.radarGapValue]}>
                    {Math.round((1 - skill.credit) * 100)}%
                  </Text>
                  <Text style={[styles.radarValue, styles.radarDemandColumn]}>
                    {skill.frequency === null ? "—" : `${Math.round(skill.frequency * 100)}%`}
                  </Text>
                </View>
              ))}
            </View>
          </>
        ) : (
          <Text style={styles.emptyText}>No role requirements are available to compare.</Text>
        )}
      </View>}

      {view === "market" && <>
        <View style={styles.card}>
          <Text style={styles.title}>Emerging this month</Text>
          <Text style={styles.description}>
            Check whether your skills are getting stale.{"\n"}
            🔥 Rising in {marketInsights.emergingRole || "target"} roles (last 30 days)
          </Text>
          {emergingSkills.length ? (
            <>
              <Text style={styles.footnote}>
                Previous 30-day window: {previousPostings} postings · Latest: {currentPostings} postings.
              </Text>
              <View style={styles.emergenceList}>
                {emergingSkills.map((item) => {
                  const movement = item.status === "rising"
                    ? `up ${formatPercentage(item.previousFrequency)} → ${formatPercentage(item.currentFrequency)}`
                    : item.status === "declining"
                      ? `down ${formatPercentage(item.previousFrequency)} → ${formatPercentage(item.currentFrequency)}`
                      : `stable at ${formatPercentage(item.currentFrequency)}`;
                  const color = item.status === "rising"
                    ? "#15803D"
                    : item.status === "declining"
                      ? "#B45353"
                      : brand.muted;
                  return (
                    <View key={item.uri} style={styles.emergenceRow}>
                      <View style={styles.emergenceSkill}>
                        <Text style={styles.relationshipSkill} numberOfLines={2}>{item.skill}</Text>
                        <Text style={[styles.emergenceMovement, { color }]}>{movement}</Text>
                      </View>
                      <Sparkline history={item.history} status={item.status} skill={item.skill} />
                    </View>
                  );
                })}
              </View>
            </>
          ) : (
            <Text style={styles.emptyText}>
              {currentPostings && previousPostings
                ? "No notable skill-demand shifts were detected in the sampled postings."
                : "Trend data needs postings in both 30-day windows for this role."}
            </Text>
          )}
          {marketInsights.emergingNote ? <Text style={styles.footnote}>{marketInsights.emergingNote}</Text> : null}
        </View>
        <View style={styles.card}>
        <Text style={styles.title}>Role demand × your skill gap</Text>
        <Text style={styles.description}>
          Posting frequency and your match credit identify gaps to focus on. This is not a salary estimate.
        </Text>
        {demandSkills.length ? (
          <>
            <Text style={styles.axisTitle}>Role-posting demand →</Text>
            <View style={styles.heatmapColumnLabels}>
              <Text style={styles.columnLabel}>Lower</Text>
              <Text style={styles.columnLabel}>Typical</Text>
              <Text style={styles.columnLabel}>Higher</Text>
            </View>
            {["High gap", "Partial gap", "Low gap"].map((label, row) => (
              <View key={label} style={styles.heatmapRow}>
                <Text style={styles.rowLabel}>{label}</Text>
                {[0, 1, 2].map((column) => (
                  <View
                    key={column}
                    style={[
                      styles.heatmapCell,
                      { backgroundColor: heatColor(2 - row, column) },
                    ]}
                  >
                    {heatmap[row * 3 + column].map((skill) => (
                      <Text key={skill.uri} style={styles.heatmapSkill} numberOfLines={2}>
                        {skill.skill}
                      </Text>
                    ))}
                  </View>
                ))}
              </View>
            ))}
            <Text style={styles.footnote}>
              Demand is relative to this role&apos;s posting profile. Skills without posting data are not plotted.
            </Text>
          </>
        ) : (
          <Text style={styles.emptyText}>
            Posting-frequency data is unavailable for this role, so a market-demand heatmap cannot be shown.
          </Text>
        )}
      </View>

        <View style={styles.card}>
        <Text style={styles.title}>High-ROI gaps</Text>
        <Text style={styles.description}>
          Frequent posting requirements are prioritized; if none reach the 50% threshold, the five most common gaps are shown.
        </Text>
        {marketInsights.highRoiGaps.length ? (
          <View style={styles.relationshipList}>
            {marketInsights.highRoiGaps.map((gap) => (
              <View key={gap.skill} style={styles.roiGap}>
                <Text style={styles.relationshipSkill}>{gap.skill}</Text>
                <Text style={styles.footnote}>
                  {gap.frequency === null ? "Posting frequency unavailable" : `${Math.round(gap.frequency * 100)}% of sampled postings`}
                  {" · "}
                  up to +{gap.readinessGainPoints} readiness points
                </Text>
                {gap.evidence ? <Text style={styles.footnote}>Resume evidence: {gap.evidence}</Text> : null}
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.emptyText}>No uncovered requirements meet the notebook&apos;s high-ROI demand threshold.</Text>
        )}
        {marketInsights.highRoiNote ? <Text style={styles.footnote}>{marketInsights.highRoiNote}</Text> : null}
        </View>
      </>}

      {view === "pathways" && <View style={styles.card}>
        <Text style={styles.title}>Skill pathways</Text>
        <Text style={styles.description}>
          Curated prerequisites show learning order; ESCO links show broader skill families or related skills.
        </Text>
        {relationships.length ? (
          <View style={styles.relationshipList}>
            {relationships.slice(0, 16).map((relationship, index) => (
              <View key={`${relationship.type}:${relationship.source}:${relationship.target}:${index}`} style={styles.relationshipRow}>
                <View style={styles.relationshipNames}>
                  <Text style={styles.relationshipSkill} numberOfLines={2}>
                    {relationship.source}
                  </Text>
                  <Text style={styles.relationshipArrow}>
                    {relationship.type === "related" ? "↔" : "→"}
                  </Text>
                  <Text style={styles.relationshipSkill} numberOfLines={2}>
                    {relationship.target}
                  </Text>
                </View>
                <View style={styles.relationshipMeta}>
                  <Text style={styles.relationshipType}>{relationshipLabel(relationship.type)}</Text>
                  <Text style={styles.relationshipStatus}>
                    {covered.includes(relationship.source) ? "Source matched" : "Source to learn"}
                    {" · "}
                    {covered.includes(relationship.target) ? "Target matched" : "Target to learn"}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.emptyText}>
            No relationships are mapped for these requirements yet. Add curated prerequisites to the backend
            configuration to show explicit learning order.
          </Text>
        )}
      </View>}
    </View>
  );
}

function formatPercentage(value: number) {
  const percentage = Math.round(value);
  return `${percentage}%`;
}

function Sparkline({
  history,
  status,
  skill,
}: {
  history: number[];
  status: "rising" | "stable" | "declining";
  skill: string;
}) {
  const width = 64;
  const height = 24;
  const padding = 3;
  const minimum = Math.min(...history);
  const maximum = Math.max(...history);
  const range = maximum - minimum;
  const points = history.map((value, index) => {
    const x = padding + (index * (width - padding * 2)) / Math.max(1, history.length - 1);
    const y = range
      ? height - padding - ((value - minimum) / range) * (height - padding * 2)
      : height / 2;
    return `${x},${y}`;
  });
  const color = status === "rising" ? "#15803D" : status === "declining" ? "#B45353" : brand.muted;

  return (
    <View accessibilityRole="image" accessibilityLabel={`${skill} demand trend`}>
      <Svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <Path d={`M ${points.join(" L ")}`} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      </Svg>
    </View>
  );
}

function heatColor(gap: number, demand: number) {
  if (gap === 2 && demand === 2) return "#FEE2E2";
  if (gap + demand >= 3) return "#FEF3C7";
  if (gap === 2 || demand === 2) return "#FFEDD5";
  return "#DCFCE7";
}

function relationshipLabel(type: AnalysisSkillRelationship["type"]) {
  if (type === "prerequisite") return "Prerequisite";
  if (type === "broader") return "Broader skill family";
  return "Related ESCO skills";
}

const styles = StyleSheet.create({
  container: { gap: 16, marginBottom: 28 },
  card: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 16,
  },
  title: { color: brand.text, fontSize: 18, fontWeight: "700", marginBottom: 6 },
  description: { color: brand.muted, fontSize: 13, lineHeight: 19, marginBottom: 16 },
  radarTable: { gap: 7 },
  radarTableHeader: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 10 },
  radarColumnHeader: { width: 40, color: brand.muted, fontSize: 9, fontWeight: "700", textAlign: "center" },
  radarSkillColumn: { flex: 1 },
  radarDemandColumn: { width: 52 },
  radarSkillRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: brand.bg,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 9,
  },
  radarSkillName: { color: brand.text, fontSize: 12, lineHeight: 16, fontWeight: "600" },
  radarSkillMeta: { color: brand.muted, fontSize: 10, lineHeight: 14, marginTop: 2 },
  radarValue: { width: 40, color: brand.text, fontSize: 11, textAlign: "center", fontWeight: "600" },
  radarCurrentValue: { color: brand.cyan },
  radarGapValue: { color: "#B45353" },
  axisTitle: { color: brand.text, fontSize: 12, fontWeight: "600", marginBottom: 6 },
  heatmapColumnLabels: { flexDirection: "row", marginLeft: 70, marginBottom: 5 },
  columnLabel: { flex: 1, textAlign: "center", color: brand.muted, fontSize: 10 },
  heatmapRow: { flexDirection: "row", gap: 4, marginBottom: 4, minHeight: 62 },
  rowLabel: { width: 66, alignSelf: "center", color: brand.muted, fontSize: 10, lineHeight: 14 },
  heatmapCell: { flex: 1, minHeight: 62, justifyContent: "center", gap: 3, borderRadius: 7, padding: 5 },
  heatmapSkill: { color: brand.text, fontSize: 10, lineHeight: 13 },
  footnote: { color: brand.muted, fontSize: 11, lineHeight: 16, marginTop: 8 },
  emergenceList: { gap: 8, marginTop: 10 },
  emergenceRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    backgroundColor: brand.bg,
    borderRadius: 10,
    paddingHorizontal: 11,
    paddingVertical: 9,
  },
  emergenceSkill: { flex: 1, gap: 3 },
  emergenceMovement: { fontSize: 11, fontWeight: "600" },
  relationshipList: { gap: 8 },
  roiGap: { backgroundColor: brand.bg, borderRadius: 10, padding: 11, gap: 3 },
  relationshipRow: {
    backgroundColor: brand.bg,
    borderRadius: 10,
    padding: 11,
    gap: 6,
  },
  relationshipNames: { flexDirection: "row", alignItems: "center", gap: 8 },
  relationshipSkill: { flex: 1, color: brand.text, fontSize: 12, fontWeight: "600", lineHeight: 16 },
  relationshipArrow: { color: brand.cyan, fontSize: 18, fontWeight: "700" },
  relationshipMeta: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", gap: 4 },
  relationshipType: { color: brand.cyan, fontSize: 11, fontWeight: "700" },
  relationshipStatus: { color: brand.muted, fontSize: 10 },
  emptyText: { color: brand.muted, fontSize: 13, lineHeight: 19 },
});
