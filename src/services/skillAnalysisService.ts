import { supabase } from "@/lib/supabase";
import type { SkillAnalysis, SkillGap } from "@/types";

export async function requestResumeParsing(resumeId: string, jobRoleId?: string) {
  const { data, error } = await supabase.functions.invoke("parse-resume", {
    body: { resume_id: resumeId, job_role_id: jobRoleId ?? null },
  });
  if (error) throw error;
  return data as { analysis_id: string };
}

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