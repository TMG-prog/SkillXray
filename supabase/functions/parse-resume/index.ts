import { createClient } from "@supabase/supabase-js";

Deno.serve(async (req) => {
  try {
    const { resume_id, job_role_id } = await req.json();
    if (!resume_id) {
      return new Response(JSON.stringify({ error: "resume_id is required" }), { status: 400 });
    }

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    await supabase.from("resumes").update({ status: "processing" }).eq("id", resume_id);

    const { data: resume, error: resumeError } = await supabase
      .from("resumes")
      .select("user_id")
      .eq("id", resume_id)
      .single();
    if (resumeError) throw resumeError;

    // --- TODO: replace this block with the real pipeline ---
    // Download the file from storage, extract text, run skill extraction,
    // map to ESCO skill IDs, compute readiness_index against job_role_id's
    // required skills, and compute per-skill gap severity.
    const MOCK_READINESS = 65;
    const MOCK_GAP_SKILLS = ["Python", "Data Analysis", "Project management"];
    // --- end mock block ---

    const { data: analysis, error: analysisError } = await supabase
      .from("skill_analyses")
      .insert({ user_id: resume.user_id, resume_id, job_role_id, readiness_index: MOCK_READINESS })
      .select()
      .single();
    if (analysisError) throw analysisError;

    for (const skillName of MOCK_GAP_SKILLS) {
      const { data: existingSkill } = await supabase
        .from("skills")
        .select("id")
        .eq("name", skillName)
        .maybeSingle();

      const skillId = existingSkill?.id ??
        (await supabase.from("skills").insert({ name: skillName }).select().single()).data?.id;

      await supabase.from("skill_gaps").insert({
        analysis_id: analysis.id,
        skill_id: skillId,
        gap_severity: 0.5,
      });
    }

    await supabase.from("resumes").update({ status: "analyzed" }).eq("id", resume_id);

    return new Response(JSON.stringify({ analysis_id: analysis.id }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error(err);
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});