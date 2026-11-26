import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";
import { buildAnalysisReport } from "./analysisReport.ts";

const require = createRequire(import.meta.url);
const pdfMake = require("pdfmake/build/pdfmake");
const fonts = require("pdfmake/build/vfs_fonts");

function analysis() {
  return {
    demo: false,
    resumeFileName: "resume.pdf",
    targetRole: "Data Analyst",
    readiness: 70,
    covered: ["SQL"],
    gaps: [{ skill: "Python", severity: "high", fill: 0 }],
    requirements: [
      { skill: "SQL", uri: "sql", weight: 0.7, credit: 1, frequency: 0.8, cv_evidence: "Used SQL for reporting." },
      { skill: "Python", uri: "python", weight: 0.3, credit: 0, frequency: null },
    ],
    learningPlan: [{
      rank: 1, skill: "Python", uri: "python", marginalGainPoints: 30, clusterGainPoints: 30,
      prerequisites: [], clusterSkills: [], coveredBy: null, hiringEvidence: null,
      resource: { title: "Learn Python", provider: "Example", url: "https://example.com/python" },
    }],
    relationships: [],
    marketInsights: {
      highRoiGaps: [],
      emergingSkills: [{
        skill: "Python", uri: "python", history: [], previousFrequency: 0.2, currentFrequency: 0.3,
        deltaPp: 10, emergenceScore: 0.5, status: "rising", evidence: "More postings mention Python.",
      }],
      currentPostings: 30, previousPostings: 40, emergingRole: "Data Analyst",
      highRoiNote: "", emergingNote: "",
    },
    warnings: [],
  };
}

test("detailed report includes evidence, recommendations and market signals in a real PDF", async () => {
  const definition = buildAnalysisReport(analysis(), new Date("2026-11-16T00:00:00Z"));
  const text = JSON.stringify(definition.content);
  for (const expected of ["Data Analyst", "70%", "Used SQL for reporting.", "Learn Python",
    "https://example.com/python", "More postings mention Python.", "Posting frequency: Unavailable"]) {
    assert.ok(text.includes(expected), `Missing ${expected}`);
  }
  const buffer = await new Promise((resolve) => pdfMake.createPdf(definition, undefined, undefined, fonts).getBuffer(resolve));
  assert.equal(buffer.subarray(0, 5).toString(), "%PDF-");
  assert.ok(buffer.length > 1000);
});

test("demo and older analyses disclose unavailable details", () => {
  const saved = analysis();
  saved.demo = true;
  saved.covered = [];
  saved.gaps = [];
  saved.requirements = [];
  saved.learningPlan = [];
  saved.marketInsights.emergingSkills = [];
  saved.warnings = ["Detailed skill results are unavailable for this older analysis."];
  const text = JSON.stringify(buildAnalysisReport(saved, new Date("2026-11-16T00:00:00Z")).content);
  assert.ok(text.includes("DEMO RESULTS"));
  assert.ok(text.includes(saved.warnings[0]));
  assert.ok(text.includes("No detailed gaps available."));
  assert.ok(text.includes("No recommendations available."));
});

test("analysis report does not invent a course link when none is curated", () => {
  const saved = analysis();
  saved.learningPlan[0].resource = null;
  const text = JSON.stringify(buildAnalysisReport(saved, new Date("2026-11-16T00:00:00Z")).content);

  assert.ok(text.includes("No exact course link is currently curated for this skill."));
  assert.ok(!text.includes("https://example.com/python"));
});
