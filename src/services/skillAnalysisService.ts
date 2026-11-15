import * as FileSystem from "expo-file-system/legacy";
import Constants from "expo-constants";
import { Platform } from "react-native";
import { decode } from "base64-arraybuffer";
import { supabase } from "@/lib/supabase";
import type { SkillAnalysis, SkillGap } from "@/types";

export interface PipelineAnalysis {
  demo?: boolean;
  role: string;
  profile_source: string;
  method: string;
  readiness: number;
  n_required: number;
  n_covered: number;
  covered: PipelineSkill[];
  gaps: PipelineSkill[];
  skill_relationships: SkillRelationship[];
  extracted_skills: Array<{ skill: string; uri: string; in_esco: boolean; mentions: number }>;
  warnings: string[];
  timings_ms: { extract: number; link: number; match: number };
  market_delta: PipelineMarketDelta;
  market_emergence?: PipelineMarketEmergence | null;
}

export interface PipelineMarketEmergence {
  role: string;
  period_days: number;
  current_postings: number;
  previous_postings: number;
  skills: PipelineEmergingSkill[];
}

export interface PipelineEmergingSkill {
  esco_uri: string;
  skill: string;
  history: number[];
  previous_frequency: number;
  current_frequency: number;
  delta_pp: number;
  emergence_score: number;
  status: "rising" | "stable" | "declining";
}

export interface PipelineSkill {
  skill: string;
  uri: string;
  weight: number;
  credit: number;
  frequency: number | null;
  reason?: string;
  evidence?: string;
  cv_evidence?: string;
  cv_highlight?: string;
  gap_confidence?: number;
}

export interface PipelineMarketDelta {
  high_roi_gaps: Array<{
    skill: string;
    frequency: number | null;
    readiness_gain_pp: number;
    evidence: string;
  }>;
  high_roi_note: string;
  emerging: null;
  emerging_note: string;
}

export interface SkillRelationship {
  source: string;
  target: string;
  type: "prerequisite" | "broader" | "related";
}

export interface CareerPivotRole {
  role: string;
  requirements: Array<{
    skill: string;
    uri: string;
    frequency: number | null;
  }>;
}

interface PickedResume {
  uri: string;
  name: string;
  mimeType?: string;
}

const API_URL = Constants.expoConfig?.extra?.apiUrl ?? process.env.EXPO_PUBLIC_API_URL;
export const USE_MOCK_ANALYSIS =
  Constants.expoConfig?.extra?.useMockAnalysis === true
  || process.env.EXPO_PUBLIC_USE_MOCK_ANALYSIS === "1";

export async function analyzeResumeFile(file: PickedResume, role: string): Promise<PipelineAnalysis> {
  if (USE_MOCK_ANALYSIS) return createMockAnalysis(role);
  const apiUrl = getApiUrl();

  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error("Please sign in first.");

  const contentType = file.mimeType ?? "application/octet-stream";
  const form = new FormData();
  form.append("role", role);
  if (Platform.OS === "web") {
    const base64 = await FileSystem.readAsStringAsync(file.uri, {
      encoding: FileSystem.EncodingType.Base64,
    });
    form.append("file", new Blob([decode(base64)], { type: contentType }), file.name);
  } else {
    const response = await FileSystem.uploadAsync(
      `${apiUrl}/analyze`,
      file.uri,
      {
        httpMethod: "POST",
        uploadType: FileSystem.FileSystemUploadType.MULTIPART,
        fieldName: "file",
        mimeType: contentType,
        parameters: { role },
        headers: { Authorization: ["Bearer", session.access_token].join(" ") },
      },
    );
    return parseAnalysisResponse(response.body, response.status);
  }

  const response = await fetch(`${apiUrl}/analyze`, {
    method: "POST",
    headers: { Authorization: ["Bearer", session.access_token].join(" ") },
    body: form,
  });

  return parseAnalysisResponse(await response.text(), response.status);
}

export async function getSupportedRoles(): Promise<string[]> {
  const apiUrl = getApiUrl();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error("Please sign in first.");

  const response = await fetch(`${apiUrl}/roles`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  });
  let result: unknown;
  try {
    result = await response.json();
  } catch {
    if (!response.ok) throw new Error(`Could not load supported roles (${response.status}).`);
    throw new Error("The roles API returned an invalid response.");
  }

  if (!response.ok) {
    const detail = isRecord(result) && typeof result.detail === "string" ? result.detail : undefined;
    throw new Error(detail ?? `Could not load supported roles (${response.status}).`);
  }
  if (!isRecord(result) || !Array.isArray(result.posting_roles)
    || !result.posting_roles.every((role) => typeof role === "string")) {
    throw new Error("The roles API returned an invalid response.");
  }
  return result.posting_roles;
}

export async function getCareerPivotRoles(): Promise<CareerPivotRole[]> {
  const apiUrl = getApiUrl();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error("Please sign in first.");

  const response = await fetch(`${apiUrl}/career-paths`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  });
  let result: unknown;
  try {
    result = await response.json();
  } catch {
    if (!response.ok) throw new Error(`Could not load career paths (${response.status}).`);
    throw new Error("The career paths API returned an invalid response.");
  }

  if (!response.ok) {
    const detail = isRecord(result) && typeof result.detail === "string" ? result.detail : undefined;
    throw new Error(detail ?? `Could not load career paths (${response.status}).`);
  }

  const isRequirement = (value: unknown): value is CareerPivotRole["requirements"][number] =>
    isRecord(value)
    && typeof value.skill === "string"
    && typeof value.uri === "string"
    && (value.frequency === null || typeof value.frequency === "number");
  const isCareerPivotRole = (value: unknown): value is CareerPivotRole =>
    isRecord(value)
    && typeof value.role === "string"
    && Array.isArray(value.requirements)
    && value.requirements.every(isRequirement);
  if (!Array.isArray(result) || !result.every(isCareerPivotRole)) {
    throw new Error("The career paths API returned an invalid response.");
  }
  return result;
}

function getApiUrl(): string {
  if (!API_URL) throw new Error("EXPO_PUBLIC_API_URL is not set.");
  return API_URL.replace(/\/+$/, "");
}

function createMockAnalysis(role: string): PipelineAnalysis {
  const skills: PipelineSkill[] = [
    { skill: "Python", uri: "demo:python", weight: 0.15, credit: 0.99, frequency: 0.82 },
    { skill: "SQL", uri: "demo:sql", weight: 0.15, credit: 0.98, frequency: 0.76 },
    { skill: "Communication", uri: "demo:communication", weight: 0.15, credit: 0.95, frequency: 0.71 },
    { skill: "Data analysis", uri: "demo:data-analysis", weight: 0.15, credit: 0.9, frequency: 0.65 },
    { skill: "Cloud computing", uri: "demo:cloud", weight: 0.2, credit: 0.45, frequency: 0.58 },
    { skill: "Machine learning", uri: "demo:machine-learning", weight: 0.2, credit: 0.4, frequency: 0.42 },
  ];
  const covered = skills.slice(0, 4);
  const gaps = skills.slice(4);

  return {
    demo: true,
    role,
    profile_source: "demo",
    method: "static sample",
    readiness: 74.3,
    n_required: skills.length,
    n_covered: covered.length,
    covered,
    gaps,
    skill_relationships: [
      { source: "Python", target: "Data analysis", type: "prerequisite" },
      { source: "SQL", target: "Data analysis", type: "related" },
      { source: "Data analysis", target: "Machine learning", type: "related" },
      { source: "Cloud computing", target: "Machine learning", type: "broader" },
    ],
    extracted_skills: covered.map(({ skill, uri }) => ({
      skill, uri, in_esco: true, mentions: 1,
    })),
    warnings: ["Demo results only: this score and these skills are sample data, not derived from your resume or target role."],
    timings_ms: { extract: 0, link: 0, match: 0 },
    market_delta: {
      high_roi_gaps: [],
      high_roi_note: "",
      emerging: null,
      emerging_note: "Demo results do not include market trend data.",
    },
    market_emergence: null,
  };
}

function parseAnalysisResponse(body: string, status: number): PipelineAnalysis {
  let result: unknown;
  try {
    result = JSON.parse(body);
  } catch {
    if (status < 200 || status >= 300) throw new Error(`Resume analysis failed (${status}).`);
    throw new Error("Analysis API returned an invalid response.");
  }

  if (status < 200 || status >= 300) {
    const detail = isRecord(result) && typeof result.detail === "string" ? result.detail : undefined;
    throw new Error(detail ?? `Resume analysis failed (${status}).`);
  }
  if (!isPipelineAnalysis(result)) throw new Error("Analysis API returned an invalid response.");
  return result;
}

function isPipelineAnalysis(value: unknown): value is PipelineAnalysis {
  if (!isRecord(value)) return false;
  const timings = value.timings_ms;
  const marketDelta = value.market_delta;
  if (!isRecord(timings)) return false;
  if (!isRecord(marketDelta) || marketDelta.emerging !== null
    || typeof marketDelta.emerging_note !== "string"
    || typeof marketDelta.high_roi_note !== "string"
    || !Array.isArray(marketDelta.high_roi_gaps)) return false;
  const isEmergingSkill = (item: unknown) =>
    isRecord(item)
    && typeof item.esco_uri === "string"
    && typeof item.skill === "string"
    && Array.isArray(item.history)
    && item.history.length === 4
    && item.history.every((point) => typeof point === "number")
    && typeof item.previous_frequency === "number"
    && typeof item.current_frequency === "number"
    && typeof item.delta_pp === "number"
    && typeof item.emergence_score === "number"
    && (item.status === "rising" || item.status === "stable" || item.status === "declining");
  const marketEmergence = value.market_emergence;
  if (marketEmergence !== undefined && marketEmergence !== null
    && (!isRecord(marketEmergence)
      || typeof marketEmergence.role !== "string"
      || marketEmergence.period_days !== 30
      || typeof marketEmergence.current_postings !== "number"
      || typeof marketEmergence.previous_postings !== "number"
      || !Array.isArray(marketEmergence.skills)
      || !marketEmergence.skills.every(isEmergingSkill))) return false;
  const isCoveredSkill = (item: unknown) =>
    isRecord(item)
    && typeof item.skill === "string"
    && typeof item.uri === "string"
    && typeof item.weight === "number"
    && typeof item.credit === "number"
    && (item.frequency === null || typeof item.frequency === "number")
    && (item.reason === undefined || typeof item.reason === "string")
    && (item.evidence === undefined || typeof item.evidence === "string")
    && (item.cv_evidence === undefined || typeof item.cv_evidence === "string")
    && (item.cv_highlight === undefined || typeof item.cv_highlight === "string")
    && (item.gap_confidence === undefined || typeof item.gap_confidence === "number");
  const isHighRoiGap = (item: unknown) =>
    isRecord(item)
    && typeof item.skill === "string"
    && (item.frequency === null || typeof item.frequency === "number")
    && typeof item.readiness_gain_pp === "number"
    && typeof item.evidence === "string";
  const isRelationship = (item: unknown) =>
    isRecord(item)
    && typeof item.source === "string"
    && typeof item.target === "string"
    && (item.type === "prerequisite" || item.type === "broader" || item.type === "related");
  const isExtractedSkill = (item: unknown) =>
    isRecord(item)
    && typeof item.skill === "string"
    && typeof item.uri === "string"
    && typeof item.in_esco === "boolean"
    && typeof item.mentions === "number";
  const result = value;
  return typeof result.role === "string"
    && typeof result.profile_source === "string"
    && typeof result.method === "string"
    && typeof result.readiness === "number"
    && result.readiness >= 0
    && result.readiness <= 100
    && typeof result.n_required === "number"
    && typeof result.n_covered === "number"
    && Array.isArray(result.covered) && result.covered.every(isCoveredSkill)
    && Array.isArray(result.gaps) && result.gaps.every(isCoveredSkill)
    && Array.isArray(result.skill_relationships) && result.skill_relationships.every(isRelationship)
    && Array.isArray(result.extracted_skills) && result.extracted_skills.every(isExtractedSkill)
    && Array.isArray(result.warnings) && result.warnings.every((warning) => typeof warning === "string")
    && marketDelta.high_roi_gaps.every(isHighRoiGap)
    && typeof timings.extract === "number"
    && typeof timings.link === "number"
    && typeof timings.match === "number";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** The skills saved for a resume, as plain names, A to Z. */
export async function getResumeSkillNames(resumeId: string): Promise<string[]> {
  const { data, error } = await supabase
    .from("resume_skills")
    .select("skills(name)")
    .eq("resume_id", resumeId);
  if (error) throw error;
  return (data ?? [])
    .map((row: any) => row.skills?.name as string | undefined)
    .filter((name): name is string => !!name)
    .sort((a, b) => a.localeCompare(b));
}

// --- Used once the skill gap analyzer exists ---------------------------------

export interface SkillGapWithName extends SkillGap {
  skill_name: string;
}

export async function getSkillGaps(analysisId: string): Promise<SkillGapWithName[]> {
  const { data, error } = await supabase
    .from("skill_gaps")
    .select("*, skills(name)")
    .eq("analysis_id", analysisId);
  if (error) throw error;
  return (data ?? []).map((row: any) => ({ ...row, skill_name: row.skills?.name ?? "Unknown skill" }));
}

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 60000;

export async function pollForAnalysis(resumeId: string): Promise<SkillAnalysis> {
  const start = Date.now();
  while (Date.now() - start < POLL_TIMEOUT_MS) {
    const { data: resume, error } = await supabase
      .from("resumes")
      .select("status")
      .eq("id", resumeId)
      .single();
    if (error) throw error;

    if (resume.status === "failed") throw new Error("Resume analysis failed.");
    if (resume.status === "analyzed") {
      const { data: analysis, error: analysisError } = await supabase
        .from("skill_analyses")
        .select("*")
        .eq("resume_id", resumeId)
        .order("created_at", { ascending: false })
        .limit(1)
        .single();
      if (analysisError) throw analysisError;
      return analysis as SkillAnalysis;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  throw new Error("Timed out waiting for resume analysis.");
}