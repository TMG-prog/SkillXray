import type { Content, TDocumentDefinitions } from "pdfmake/interfaces";
import type { Analysis, AnalysisRequirement } from "@/state/appdatacontext";

const percentage = (value: number) => `${Math.round(value * 100)}%`;

function requirementDetails(requirement: AnalysisRequirement): Content[] {
  const details: Content[] = [
    { text: requirement.skill, style: "itemTitle" },
    {
      text: `Match: ${percentage(requirement.credit)}  |  Role weight: ${percentage(requirement.weight)}  |  Posting frequency: ${
        requirement.frequency === null ? "Unavailable" : percentage(requirement.frequency)
      }`,
      style: "muted",
    },
  ];
  if (requirement.reason) details.push({ text: `Match reason: ${requirement.reason}`, style: "detail" });
  if (requirement.evidence) details.push({ text: `Matching evidence: ${requirement.evidence}`, style: "detail" });
  if (requirement.cv_evidence) {
    details.push({ text: `CV excerpt: ${requirement.cv_evidence}`, style: "detail" });
  } else {
    details.push({ text: "CV excerpt unavailable.", style: "muted" });
  }
  if (requirement.gap_confidence !== undefined) {
    details.push({ text: `Gap confidence: ${percentage(requirement.gap_confidence)}`, style: "muted" });
  }
  return details;
}

export function buildAnalysisReport(analysis: Analysis, generatedAt: Date): TDocumentDefinitions {
  const content: Content[] = [
    { text: "SkillXray", style: "brand" },
    { text: "Career readiness report", style: "title" },
    { text: `Target role: ${analysis.targetRole}`, style: "subtitle" },
    { text: `Resume: ${analysis.resumeFileName}`, style: "muted" },
    { text: `Report generated: ${generatedAt.toISOString().slice(0, 10)} (UTC)`, style: "muted" },
  ];

  if (analysis.demo) {
    content.push({ text: "DEMO RESULTS: this report was not calculated from your resume.", style: "notice" });
  }
  content.push(
    { text: "Readiness", style: "heading" },
    { text: `${Math.round(analysis.readiness)}%`, style: "score" },
    { text: `${analysis.covered.length} matched skills and ${analysis.gaps.length} identified gaps.`, style: "detail" },
  );

  if (analysis.warnings.length) {
    content.push({ text: "Important notes", style: "heading" });
    for (const warning of analysis.warnings) content.push({ text: warning, style: "detail" });
  }

  const covered = new Set(analysis.covered);
  const matchedRequirements = analysis.requirements.filter((item) => covered.has(item.skill));
  const gapRequirements = analysis.requirements.filter((item) => !covered.has(item.skill));
  content.push({ text: "Matched skills and CV evidence", style: "heading" });
  if (matchedRequirements.length) {
    for (const requirement of matchedRequirements) content.push(...requirementDetails(requirement));
  } else {
    content.push({ text: analysis.covered.length ? analysis.covered.join(", ") : "No matched requirements available.", style: "detail" });
  }

  content.push({ text: "Identified skill gaps", style: "heading" });
  if (gapRequirements.length) {
    for (const requirement of gapRequirements) {
      const gap = analysis.gaps.find((item) => item.skill === requirement.skill);
      if (gap) content.push({ text: `${gap.severity.toUpperCase()} PRIORITY`, style: "label" });
      content.push(...requirementDetails(requirement));
    }
  } else if (analysis.gaps.length) {
    for (const gap of analysis.gaps) {
      content.push({ text: `${gap.skill} — ${gap.severity} priority; ${percentage(gap.fill)} match`, style: "detail" });
    }
  } else {
    content.push({ text: "No detailed gaps available.", style: "detail" });
  }

  content.push({ text: "Learning recommendations", style: "heading" });
  if (analysis.learningPlan?.length) {
    for (const step of analysis.learningPlan) {
      content.push(
        { text: `${step.rank}. ${step.skill}`, style: "itemTitle" },
        { text: `${step.resource.title} — ${step.resource.provider}`, style: "detail" },
        { text: step.resource.url, style: "link" },
        { text: `Estimated readiness gain: up to +${step.marginalGainPoints.toFixed(1)} points`, style: "muted" },
      );
      if (step.prerequisites.length) content.push({ text: `Learn after: ${step.prerequisites.join(", ")}`, style: "detail" });
      if (step.clusterSkills.length) content.push({ text: `Related skills: ${step.clusterSkills.join(", ")}`, style: "detail" });
      if (step.coveredBy) content.push({ text: `Also addressed by: ${step.coveredBy}`, style: "detail" });
      if (step.hiringEvidence?.evidence) content.push({ text: `Hiring evidence: ${step.hiringEvidence.evidence}`, style: "detail" });
    }
  } else if (analysis.gaps.length) {
    for (const gap of analysis.gaps) {
      content.push(
        { text: `Find courses for ${gap.skill}`, style: "itemTitle" },
        { text: `https://www.coursera.org/search?query=${encodeURIComponent(gap.skill)}`, style: "link" },
      );
    }
  } else {
    content.push({ text: "No recommendations available.", style: "detail" });
  }

  const market = analysis.marketInsights;
  content.push(
    { text: "Market insights", style: "heading" },
    { text: `Role: ${market.emergingRole || analysis.targetRole}. Recent postings: ${market.currentPostings}; baseline postings: ${market.previousPostings}.`, style: "detail" },
  );
  if (market.recentWindowStart && market.recentWindowEnd) {
    content.push({ text: `Recent window: ${market.recentWindowStart} to ${market.recentWindowEnd}`, style: "muted" });
  }
  if (market.baselineWindowStart && market.baselineWindowEnd) {
    content.push({ text: `Baseline window: ${market.baselineWindowStart} to ${market.baselineWindowEnd}`, style: "muted" });
  }
  if (market.highRoiNote) content.push({ text: market.highRoiNote, style: "detail" });
  for (const gap of market.highRoiGaps ?? []) {
    content.push(
      { text: gap.skill, style: "itemTitle" },
      { text: `Posting frequency: ${gap.frequency === null ? "Unavailable" : percentage(gap.frequency)}; estimated readiness gain: up to +${gap.readinessGainPoints.toFixed(1)} points`, style: "detail" },
    );
    if (gap.evidence) content.push({ text: `Resume evidence: ${gap.evidence}`, style: "detail" });
    if (gap.hiringEvidence) content.push({ text: `Hiring evidence: ${gap.hiringEvidence}`, style: "detail" });
  }
  if (market.emergingNote) content.push({ text: market.emergingNote, style: "detail" });
  if (market.trendDataSufficient === false) {
    content.push({ text: "The posting sample is insufficient for reliable trend comparisons.", style: "detail" });
  }
  for (const skill of market.emergingSkills ?? []) {
    content.push(
      { text: `${skill.skill} — ${skill.status}`, style: "itemTitle" },
      { text: `Baseline: ${percentage(skill.previousFrequency)}; recent: ${percentage(skill.currentFrequency)}; change: ${skill.deltaPp.toFixed(1)} percentage points${skill.confidence ? `; confidence: ${skill.confidence}` : ""}`, style: "detail" },
    );
    if (skill.evidence) content.push({ text: skill.evidence, style: "detail" });
    for (const sample of skill.samplePostings ?? []) {
      content.push({ text: `Example: ${sample.title} — ${sample.postedAt}${sample.publisher ? ` — ${sample.publisher}` : ""}`, style: "muted" });
    }
  }

  if (analysis.relationships.length) {
    content.push({ text: "Skill pathways", style: "heading" });
    for (const relationship of analysis.relationships) {
      content.push({ text: `${relationship.source} — ${relationship.type} — ${relationship.target}`, style: "detail" });
    }
  }
  if (analysis.extractedSkills?.length) {
    content.push({ text: "Extracted skills", style: "heading" });
    content.push({ text: analysis.extractedSkills.map((skill) => skill.skill).join(", "), style: "detail" });
  }

  return {
    info: { title: "SkillXray career readiness report", subject: analysis.targetRole },
    pageSize: "A4",
    pageMargins: [44, 44, 44, 44],
    content,
    defaultStyle: { font: "Roboto", fontSize: 10, color: "#1d2939" },
    styles: {
      brand: { fontSize: 11, bold: true, color: "#087f8c", margin: [0, 0, 0, 6] },
      title: { fontSize: 23, bold: true, margin: [0, 0, 0, 8] },
      subtitle: { fontSize: 13, bold: true, margin: [0, 0, 0, 4] },
      heading: { fontSize: 15, bold: true, color: "#087f8c", margin: [0, 18, 0, 8] },
      score: { fontSize: 26, bold: true, color: "#087f8c" },
      itemTitle: { fontSize: 11, bold: true, margin: [0, 10, 0, 3] },
      label: { fontSize: 8, bold: true, color: "#9a5700", margin: [0, 8, 0, 0] },
      detail: { margin: [0, 3, 0, 3], lineHeight: 1.2 },
      muted: { fontSize: 9, color: "#526071", margin: [0, 2, 0, 2], lineHeight: 1.2 },
      link: { fontSize: 9, color: "#087f8c", margin: [0, 2, 0, 2] },
      notice: { bold: true, color: "#8a5300", margin: [0, 12, 0, 0] },
    },
  };
}
