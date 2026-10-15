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
const FASTAPI_EXTRACT_URL = "https://your-fastapi-backend.com/api/v1/extract-skills"; // Update with your deployed backend URL

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
  const resume = data as Resume;

  // 3. (Optional Client-Side Trigger) Extract text and call your FastAPI JobBERT model
  // Note: For production, you'd typically handle text extraction via a Supabase Edge Function 
  // if you are uploading PDFs, but if you pass raw text or parsed strings, call it here:
  try {
    // Assuming you have parsed the resume text or have it ready:
    // const extractedText = await parsePdfText(file.uri); 
    
    /* 
    await fetch(FASTAPI_EXTRACT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_id: resume.id, text: extractedText }),
    });
    */
  } catch (extractionError) {
    console.error("Failed to trigger skill extraction:", extractionError);
  }

  return resume;
}

export async function getResume(resumeId: string): Promise<Resume> {
  const { data, error } = await supabase.from("resumes").select("*").eq("id", resumeId).single();
  if (error) throw error;
  return data as Resume;
}