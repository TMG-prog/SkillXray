import * as FileSystem from "expo-file-system/legacy";
import { decode } from "base64-arraybuffer";
import { supabase } from "@/lib/supabase";
import type { Resume } from "@/types";

interface PickedFile {
  uri: string;
  name: string;
  mimeType?: string;
}

export interface ExtractedSkill {
  skill: string;
  confidence: number | null;
}

const RESUME_BUCKET = "resumes";
// Set EXPO_PUBLIC_API_URL in .env, e.g. https://your-backend.example.com
const API_URL = process.env.EXPO_PUBLIC_API_URL;

export async function uploadResume(file: PickedFile, userId: string): Promise<Resume> {
  const base64 = await FileSystem.readAsStringAsync(file.uri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  const arrayBuffer = decode(base64);

  // Folder-per-user path, required by the storage RLS policy
  const path = `${userId}/${Date.now()}-${file.name}`;

  // 1. Upload file to Supabase Storage
  const { error: uploadError } = await supabase.storage
    .from(RESUME_BUCKET)
    .upload(path, arrayBuffer, {
      contentType: file.mimeType ?? "application/octet-stream",
      upsert: false,
    });
  if (uploadError) throw uploadError;

  // 2. Insert record into resumes table
  const { data, error } = await supabase
    .from("resumes")
    .insert({ user_id: userId, file_url: path, status: "uploaded" })
    .select()
    .single();
  if (error) throw error;

  return data as Resume;
}

/**
 * 3. Ask the backend to read the uploaded resume, run the skill extractor and
 * save the skills to `resume_skills`. The app sends only the resume id and the
 * user's session token; the backend fetches the file itself.
 */
export async function extractResumeSkills(resumeId: string): Promise<ExtractedSkill[]> {
  if (!API_URL) throw new Error("EXPO_PUBLIC_API_URL is not set.");

  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error("Please sign in first.");

  const res = await fetch(`${API_URL}/api/v1/extract-skills`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({ resume_id: resumeId }),
  });

  if (!res.ok) {
    let detail: string | undefined;
    try {
      detail = (await res.json()).detail;
    } catch {}
    throw new Error(detail ?? `Skill extraction failed (${res.status}).`);
  }

  const body = await res.json();
  return body.skills as ExtractedSkill[];
}

export async function getResumeSkills(resumeId: string): Promise<ExtractedSkill[]> {
  const { data, error } = await supabase
    .from("resume_skills")
    .select("skill, confidence")
    .eq("resume_id", resumeId)
    .order("confidence", { ascending: false });
  if (error) throw error;
  return data as ExtractedSkill[];
}

export async function getResume(resumeId: string): Promise<Resume> {
  const { data, error } = await supabase.from("resumes").select("*").eq("id", resumeId).single();
  if (error) throw error;
  return data as Resume;
}