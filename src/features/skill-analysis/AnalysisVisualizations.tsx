import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Line, Polygon } from "react-native-svg";
import type {
  AnalysisMarketInsights,
  AnalysisRequirement,
  AnalysisSkillRelationship,
} from "@/state/appdatacontext";
import { brand } from "@/components/ui/theme";

const CHART_SIZE = 250;
const CHART_CENTER = CHART_SIZE / 2;
const CHART_RADIUS = 88;

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
  const radarSkills = [...requirements]
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 6);
  const demandSkills = requirements.filter((skill) => skill.frequency !== null);
  const demandMaximum = Math.max(0, ...demandSkills.map((skill) => skill.frequency ?? 0));
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
          Your match credit compared with the full target for the role&apos;s most important skills.
        </Text>
        {radarSkills.length >= 3 ? (
          <>
            <RadarChart skills={radarSkills} />
            <View style={styles.legend}>
              <View style={[styles.legendLine, styles.currentLegend]} />
              <Text style={styles.legendText}>Your match</Text>
              <View style={[styles.legendLine, styles.targetLegend]} />
              <Text style={styles.legendText}>Target (100%)</Text>
            </View>
            <View style={styles.radarSkillList}>
              {radarSkills.map((skill) => (
                <View key={skill.uri} style={styles.radarSkillRow}>
                  <Text style={styles.radarSkillName} numberOfLines={2}>{skill.skill}</Text>
                  <Text style={styles.radarSkillScore}>{Math.round(skill.credit * 100)}%</Text>
                </View>
              ))}
            </View>
          </>
        ) : (
          <Text style={styles.emptyText}>At least three role requirements are needed for a radar chart.</Text>
        )}
      </View>}

      {view === "market" && <View style={styles.card}>
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
      </View>}

      {view === "market" && <View style={styles.card}>
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
        <Text style={styles.footnote}>{marketInsights.emergingNote}</Text>
      </View>}

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

function RadarChart({ skills }: { skills: AnalysisRequirement[] }) {
  const angleFor = (index: number) => (Math.PI * 2 * index) / skills.length - Math.PI / 2;
  const pointFor = (index: number, value: number) => {
    const angle = angleFor(index);
    const radius = CHART_RADIUS * Math.max(0, Math.min(1, value));
    return `${CHART_CENTER + Math.cos(angle) * radius},${CHART_CENTER + Math.sin(angle) * radius}`;
  };
  const targetPoints = skills.map((_, index) => pointFor(index, 1)).join(" ");
  const currentPoints = skills.map((skill, index) => pointFor(index, skill.credit)).join(" ");

  return (
    <View style={styles.chartWrap} accessibilityLabel="Radar chart showing resume match against target requirements">
      <Svg width={CHART_SIZE} height={CHART_SIZE}>
        {[0.25, 0.5, 0.75, 1].map((level) => (
          <Polygon
            key={level}
            points={skills.map((_, index) => pointFor(index, level)).join(" ")}
            fill="none"
            stroke={brand.border}
            strokeWidth={1}
          />
        ))}
        {skills.map((skill, index) => {
          const angle = angleFor(index);
          return (
            <Line
              key={skill.uri}
              x1={CHART_CENTER}
              y1={CHART_CENTER}
              x2={CHART_CENTER + Math.cos(angle) * CHART_RADIUS}
              y2={CHART_CENTER + Math.sin(angle) * CHART_RADIUS}
              stroke={brand.border}
              strokeWidth={1}
            />
          );
        })}
        <Polygon
          points={targetPoints}
          fill="none"
          stroke={brand.muted}
          strokeWidth={2}
          strokeDasharray="5 4"
        />
        <Polygon
          points={currentPoints}
          fill="rgba(0, 122, 135, 0.2)"
          stroke={brand.cyan}
          strokeWidth={2}
        />
        {skills.map((skill, index) => {
          const point = pointFor(index, skill.credit).split(",").map(Number);
          return <Circle key={skill.uri} cx={point[0]} cy={point[1]} r={4} fill={brand.cyan} />;
        })}
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
  chartWrap: { alignItems: "center", marginVertical: 2 },
  legend: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 7, marginBottom: 14 },
  legendLine: { width: 20, height: 0, borderTopWidth: 2 },
  currentLegend: { borderColor: brand.cyan },
  targetLegend: { borderColor: brand.muted, borderStyle: "dashed" },
  legendText: { color: brand.muted, fontSize: 12, marginRight: 6 },
  radarSkillList: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  radarSkillRow: {
    width: "48%",
    minHeight: 40,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
    backgroundColor: brand.bg,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  radarSkillName: { flex: 1, color: brand.text, fontSize: 12, lineHeight: 16 },
  radarSkillScore: { color: brand.cyan, fontWeight: "700", fontSize: 12 },
  axisTitle: { color: brand.text, fontSize: 12, fontWeight: "600", marginBottom: 6 },
  heatmapColumnLabels: { flexDirection: "row", marginLeft: 70, marginBottom: 5 },
  columnLabel: { flex: 1, textAlign: "center", color: brand.muted, fontSize: 10 },
  heatmapRow: { flexDirection: "row", gap: 4, marginBottom: 4, minHeight: 62 },
  rowLabel: { width: 66, alignSelf: "center", color: brand.muted, fontSize: 10, lineHeight: 14 },
  heatmapCell: { flex: 1, minHeight: 62, justifyContent: "center", gap: 3, borderRadius: 7, padding: 5 },
  heatmapSkill: { color: brand.text, fontSize: 10, lineHeight: 13 },
  footnote: { color: brand.muted, fontSize: 11, lineHeight: 16, marginTop: 8 },
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
