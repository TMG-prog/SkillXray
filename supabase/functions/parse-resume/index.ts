import { createClient } from "npm:@supabase/supabase-js@2";
import { strFromU8, unzipSync } from "npm:fflate@0.8.2";
import { extractText, getDocumentProxy } from "npm:unpdf@0.12.1";

const BUCKET = "resumes";
const FILE_PATH_COLUMN = "file_url";
const MAX_FILE_BYTES = 8 * 1024 * 1024;
const MAX_TEXT_CHARS = 60_000;

type Parsed = {
  text: string;
  sections: Record<string, string>;
  contact: { email: string | null; phone: string | null };
};

class ParseError extends Error {
  status: number;
  constructor(message: string, status = 422) {
    super(message);
    this.status = status;
  }
}

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });

function detectType(b: Uint8Array): "pdf" | "docx" | "unknown" {
  if (b[0] === 0x25 && b[1] === 0x50 && b[2] === 0x44 && b[3] === 0x46) return "pdf";
  if (b[0] === 0x50 && b[1] === 0x4b) return "docx";
  return "unknown";
}

async function pdfToText(bytes: Uint8Array): Promise<string> {
  const pdf = await getDocumentProxy(bytes);
  const result = await extractText(pdf, { mergePages: true });
  const text = Array.isArray(result.text) ? result.text.join("\n") : result.text;
  return text ?? "";
}

function docxToText(bytes: Uint8Array): string {
  const files = unzipSync(bytes, { filter: (f) => f.name === "word/document.xml" });
  const xml = files["word/document.xml"];
  if (!xml) throw new ParseError("This Word file has no readable content.");
  return strFromU8(xml)
    .replace(/<w:tab\/>/g, "\t")
    .replace(/<w:br\/>/g, "\n")
    .replace(/<\/w:p>/g, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

const clean = (t: string | null | undefined) =>
  (t ?? "")
    .replace(/\r/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

function splitSections(text: string): Record<string, string> {
  const buckets: Record<string, string[]> = { header: [] };
  let current = "header";

  const SECTION_HEADINGS: Record<string, RegExp> = {
    summary: /^(summary|professional summary|profile|objective|about me)$/i,
    experience: /^(work experience|professional experience|experience|employment( history)?)$/i,
    education: /^(education|academic background|qualifications)$/i,
    skills: /^(skills|technical skills|key skills|core competencies|competencies)$/i,
    projects: /^(projects|personal projects)$/i,
    certifications: /^(certifications?|licenses( & certifications)?|courses)$/i,
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const heading = line.replace(/[:\s]+$/, "");
    const key = line.length < 40
      ? Object.entries(SECTION_HEADINGS).find(([, re]) => re.test(heading))?.[0]
      : undefined;

    if (key) {
      current = key;
      buckets[current] ??= [];
      continue;
    }
    (buckets[current] ??= []).push(line);
  }

  const sections: Record<string, string> = {};
  for (const [name, lines] of Object.entries(buckets)) {
    const body = lines.join("\n").trim();
    if (body) sections[name] = body;
  }
  return sections;
}

function extractContact(text: string) {
  return {
    email: text.match(/[\w.+-]+@[\w-]+\.[\w.-]+/)?.[0] ?? null,
    phone: text.match(/\+?\d[\d\s().-]{7,}\d/)?.[0]?.trim() ?? null,
  };
}

async function parseResume(bytes: Uint8Array): Promise<Parsed> {
  const kind = detectType(bytes);
  if (kind === "unknown") {
    throw new ParseError("Unsupported file. Upload a PDF or a .docx file.", 415);
  }

  let raw: string;
  try {
    raw = kind === "pdf" ? await pdfToText(bytes) : docxToText(bytes);
  } catch (e) {
    if (e instanceof ParseError) throw e;
    throw new ParseError("Could not read this file. It may be corrupted or password-protected.");
  }

  const text = clean(raw).slice(0, MAX_TEXT_CHARS);
  if (text.length < 50) {
    throw new ParseError("No readable text found. If this is a scanned PDF, export a text version and try again.");
  }

  return { text, sections: splitSections(text), contact: extractContact(text) };
}

async function extractSkillsFromModel(text: string): Promise<string[]> {
  const modelUrl = Deno.env.get("MODEL_URL");
  if (!modelUrl) throw new Error("MODEL_URL environment variable is not set.");

  const res = await fetch(modelUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${Deno.env.get("MODEL_API_KEY") ?? ""}`,
    },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) throw new Error(`Model extraction service returned status ${res.status}`);
  const data = await res.json();
  return data.skills ?? [];
}

async function getSkillIds(supabase: any, names: string[]): Promise<Record<string, string>> {
  if (!names.length) return {};
  const { data: existing, error } = await supabase
    .from("skills")
    .select("id, name")
    .in("name", names);
  if (error) throw new Error(`Loading skills failed: ${error.message}`);

  const ids: Record<string, string> = {};
  for (const s of existing ?? []) ids[s.name] = s.id;

  const missing = names.filter((n) => !ids[n]);
  if (missing.length) {
    const { data: created, error: insErr } = await supabase
      .from("skills")
      .insert(missing.map((name) => ({ name })))
      .select("id, name");
    if (insErr) throw new Error(`Creating skills failed: ${insErr.message}`);
    for (const s of created ?? []) ids[s.name] = s.id;
  }
  return ids;
}

async function handle(req: Request): Promise<Response> {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );
  let resumeId: string | null = null;

  try {
    const token = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "");
    const { data: { user }, error: authErr } = await supabase.auth.getUser(token);
    if (authErr || !user) return json({ error: "Not signed in." }, 401);

    const body = await req.json().catch(() => ({}));
    resumeId = body.resume_id ?? body.resumeId ?? null;
    if (!resumeId) return json({ error: "resume_id is required" }, 400);

    const { data: resume, error: resumeErr } = await supabase
      .from("resumes")
      .select("*")
      .eq("id", resumeId)
      .eq("user_id", user.id)
      .single();
    if (resumeErr || !resume) {
      return json({ error: `Resume not found: ${resumeErr?.message ?? "no row"}` }, 404);
    }

    const rawPath = resume[FILE_PATH_COLUMN];
    if (!rawPath) return json({ error: "File path is empty for this resume." }, 500);

    const path = decodeURIComponent(String(rawPath).split("?")[0].replace(/^.*\/resumes\//, ""));

    const { data: file, error: dlErr } = await supabase.storage.from(BUCKET).download(path);
    if (dlErr || !file) return json({ error: `Could not download file: ${dlErr?.message}` }, 500);
    if (file.size > MAX_FILE_BYTES) throw new ParseError("File is too large. Keep it under 8 MB.", 413);

    // 1. Parse text from PDF/DOCX
    const parsed = await parseResume(new Uint8Array(await file.arrayBuffer()));

    await supabase
      .from("resumes")
      .update({
        parsed_text: parsed.text,
        parsed_data: { sections: parsed.sections, contact: parsed.contact },
      })
      .eq("id", resumeId);

    // 2. Extract skills using your fine-tuned JobBERT model via FastAPI
    const extractedSkills = await extractSkillsFromModel(parsed.text);

    if (extractedSkills.length > 0) {
      const skillIds = await getSkillIds(supabase, extractedSkills);

      // 3. Save into resume_skills table
      const { error: rsErr } = await supabase.from("resume_skills").upsert(
        extractedSkills.map((skillName) => ({
          resume_id: resumeId,
          skill_id: skillIds[skillName],
        })),
        { onConflict: "resume_id,skill_id" }
      );
      if (rsErr) return json({ error: `Saving resume skills failed: ${rsErr.message}` }, 500);
    }

    // 4. Mark status as analyzed
    await supabase.from("resumes").update({ status: "analyzed" }).eq("id", resumeId);

    return json({ success: true, resume_id: resumeId, skills_extracted: extractedSkills.length });
  } catch (e) {
    if (resumeId) {
      try { await supabase.from("resumes").update({ status: "failed" }).eq("id", resumeId); } catch (_) {}
    }
    if (e instanceof ParseError) return json({ error: e.message }, e.status);
    return json({ error: e instanceof Error ? e.message : "Unexpected error" }, 500);
  }
}

Deno.serve(async (req) => {
  try {
    return await handle(req);
  } catch (e) {
    return json({ error: e instanceof Error ? e.message : "Unexpected error" }, 500);
  }
});