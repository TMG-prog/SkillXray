import * as FileSystem from "expo-file-system/legacy";
import { decode } from "base64-arraybuffer";
import { supabase } from "@/lib/supabase";
import type { Resume } from "@/types";

interface PickedFile {
  uri: string;
  name: string;
  mimeType?: string;
}

const RESUME_BUCKET = "resumes";

export async function uploadResume(file: PickedFile, userId: string): Promise<Resume> {
  const base64 = await FileSystem.readAsStringAsync(file.uri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  const arrayBuffer = decode(base64);

  // Folder-per-user path, required by the storage RLS policy below
  const path = `${userId}/${Date.now()}-${file.name}`;

  const { error: uploadError } = await supabase.storage
    .from(RESUME_BUCKET)
    .upload(path, arrayBuffer, {
      contentType: file.mimeType ?? "application/octet-stream",
      upsert: false,
    });
  if (uploadError) throw uploadError;

  const { data, error } = await supabase
    .from("resumes")
    .insert({ user_id: userId, file_url: path, status: "uploaded" })
    .select()
    .single();
  if (error) throw error;
  return data as Resume;
}

export async function getResume(resumeId: string): Promise<Resume> {
  const { data, error } = await supabase.from("resumes").select("*").eq("id", resumeId).single();
  if (error) throw error;
  return data as Resume;
}