import { supabase } from "@/lib/supabase";
import type { SkillAnalysis } from "@/types";

export async function getLatestSkillAnalysis(profileId: string): Promise<SkillAnalysis | null> {
  const { data, error } = await supabase
    .from("SkillAnalyses")
    .select("*")
    .eq("profileId", profileId)
    .order("createdAt", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) throw error;
  return data;
}
