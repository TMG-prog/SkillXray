import { supabase } from "@/lib/supabase";
import type { Analysis, AnalysisHistoryEntry } from "@/state/appdatacontext";
import { COURSE_TRUST_SIGNALS, type CourseTrustSignal } from "@/types";

interface AnalysisRow {
  id: string;
  resume_id: string;
  job_role_id: string | null;
  readiness_index: number | string;
  created_at: string;
  result_data: unknown;
}

interface ResumeRow {
  id: string;
  file_url: string;
}

interface JobRoleRow {
  id: string;
  title: string;
}

const HISTORY_LIMIT = 50;

export async function saveAnalysisHistory(
  analysis: Analysis,
  userId: string,
  resumeId: string,
  roleTitle: string,
): Promise<AnalysisHistoryEntry> {
  const { data: roles, error: roleError } = await supabase
    .from("job_roles")
    .select("id")
    .eq("title", roleTitle)
    .limit(2);
  if (roleError) throw roleError;
  const roleId = roles?.length === 1 ? roles[0].id : null;

  const { data, error } = await supabase
    .from("skill_analyses")
    .insert({
      user_id: userId,
      resume_id: resumeId,
      job_role_id: roleId,
      readiness_index: analysis.readiness,
      result_data: analysis,
    })
    .select("id, created_at")
    .single();
  if (error) throw error;

  return {
    id: data.id,
    createdAt: data.created_at,
    analysis,
  };
}

export async function getAnalysisHistory(userId: string): Promise<AnalysisHistoryEntry[]> {
  const { data, error } = await supabase
    .from("skill_analyses")
    .select("id, resume_id, job_role_id, readiness_index, created_at, result_data")
    .eq("user_id", userId)
    .order("created_at", { ascending: false })
    .limit(HISTORY_LIMIT);
  if (error) throw error;

  const rows = (data ?? []) as AnalysisRow[];
  if (!rows.length) return [];

  const resumeIds = [...new Set(rows.map((row) => row.resume_id))];
  const roleIds = [...new Set(rows.flatMap((row) => row.job_role_id ? [row.job_role_id] : []))];
  const [resumesResult, rolesResult] = await Promise.all([
    supabase.from("resumes").select("id, file_url").in("id", resumeIds),
    roleIds.length
      ? supabase.from("job_roles").select("id, title").in("id", roleIds)
      : Promise.resolve({ data: [], error: null }),
  ]);
  if (resumesResult.error) throw resumesResult.error;
  if (rolesResult.error) throw rolesResult.error;

  const resumes = new Map(
    ((resumesResult.data ?? []) as ResumeRow[]).map((resume) => [resume.id, resume.file_url]),
  );
  const roles = new Map(
    ((rolesResult.data ?? []) as JobRoleRow[]).map((role) => [role.id, role.title]),
  );

  return rows.map((row) => ({
    id: row.id,
    createdAt: row.created_at,
    analysis: isAnalysis(row.result_data)
      ? row.result_data
      : unavailableAnalysis(row, resumes.get(row.resume_id), roles.get(row.job_role_id ?? "")),
  }));
}

function isAnalysis(value: unknown): value is Analysis {
  if (!isRecord(value)) return false;
  return typeof value.resumeFileName === "string"
    && typeof value.targetRole === "string"
    && typeof value.readiness === "number"
    && Array.isArray(value.gaps)
    && Array.isArray(value.covered)
    && Array.isArray(value.requirements)
    && Array.isArray(value.relationships)
    && isRecord(value.marketInsights)
    && (value.learningPlan === undefined
      || (Array.isArray(value.learningPlan) && value.learningPlan.every(isLearningPlanStep)))
    && Array.isArray(value.warnings);
}

function isLearningPlanStep(value: unknown): boolean {
  if (!isRecord(value) || !isRecord(value.resource)) return false;
  return typeof value.rank === "number"
    && typeof value.skill === "string"
    && typeof value.uri === "string"
    && typeof value.marginalGainPoints === "number"
    && typeof value.clusterGainPoints === "number"
    && Array.isArray(value.prerequisites)
    && value.prerequisites.every((skill) => typeof skill === "string")
    && Array.isArray(value.clusterSkills)
    && value.clusterSkills.every((skill) => typeof skill === "string")
    && (value.coveredBy === null || typeof value.coveredBy === "string")
    && (value.hiringEvidence === null || isRecord(value.hiringEvidence))
    && typeof value.resource.title === "string"
    && typeof value.resource.provider === "string"
    && typeof value.resource.url === "string"
    && (value.resource.trustSignals === undefined
      || (Array.isArray(value.resource.trustSignals)
        && value.resource.trustSignals.every(isCourseTrustSignal)))
    && (value.resource.trustEvidenceUrl === undefined
      || value.resource.trustEvidenceUrl === null
      || isHttpUrl(value.resource.trustEvidenceUrl))
    && (!(Array.isArray(value.resource.trustSignals) && value.resource.trustSignals.length > 0)
      || isHttpUrl(value.resource.trustEvidenceUrl));
}

function isCourseTrustSignal(value: unknown): value is CourseTrustSignal {
  return COURSE_TRUST_SIGNALS.some((signal) => signal === value);
}

function isHttpUrl(value: unknown): value is string {
  return typeof value === "string" && /^https?:\/\/\S+$/i.test(value);
}

function unavailableAnalysis(row: AnalysisRow, fileUrl?: string, roleTitle?: string): Analysis {
  const readiness = Number(row.readiness_index);
  return {
    demo: false,
    resumeFileName: fileUrl?.split("/").pop() || "Resume",
    targetRole: roleTitle || "Unknown role",
    readiness: Number.isFinite(readiness) ? readiness : 0,
    gaps: [],
    covered: [],
    requirements: [],
    learningPlan: [],
    relationships: [],
    marketInsights: {
      highRoiGaps: [],
      emergingSkills: [],
      currentPostings: 0,
      previousPostings: 0,
      emergingRole: roleTitle || "target",
      highRoiNote: "",
      emergingNote: "This older analysis does not have a saved detailed report.",
    },
    warnings: ["Detailed skill results are unavailable for this older analysis."],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
