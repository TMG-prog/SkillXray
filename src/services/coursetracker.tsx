import { supabase } from "@/lib/supabase";
import type { TrackedCourse } from "@/types";

export async function listTrackedCourses(profileId: string): Promise<TrackedCourse[]> {
  const { data, error } = await supabase
    .from("TrackedCourses")
    .select("*")
    .eq("profileId", profileId)
    .order("deadline", { ascending: true, nullsFirst: false });
  if (error) throw error;
  return data ?? [];
}

export async function addTrackedCourse(course: Omit<TrackedCourse, "id">): Promise<TrackedCourse> {
  const { data, error } = await supabase
    .from("TrackedCourses")
    .insert(course)
    .select()
    .single();
  if (error) throw error;
  return data;
}

export async function updateTrackedCourseStatus(id: string, status: TrackedCourse["status"]): Promise<void> {
  const { error } = await supabase.from("TrackedCourses").update({ status }).eq("id", id);
  if (error) throw error;
}

export async function deleteTrackedCourse(id: string): Promise<void> {
  const { error } = await supabase.from("TrackedCourses").delete().eq("id", id);
  if (error) throw error;
}