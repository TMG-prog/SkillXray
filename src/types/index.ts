export interface Profile {
  id: string;
  fullName: string;
  email: string;
}

export interface Resume {
  id: string;
  user_id: string;
  file_url: string;
  status: "uploaded" | "processing" | "analyzed" | "failed";
  uploaded_at: string;
}

export interface SkillAnalysis {
  id: string;
  user_id: string;
  resume_id: string;
  job_role_id: string;
  readiness_index: number;
  created_at: string;
}

export interface SkillGap {
  id: string;
  analysis_id: string;
  skill_id: string;
  gap_severity: number;
}

export interface Skill {
  id: string;
  name: string;
  escoUri?: string;
}

export interface JobRole {
  id: string;
  title: string;
  description: string;
}



export interface LearningResource {
  id: string;
  title: string;
  provider: string;
  url: string;
  trustSignals?: CourseTrustSignal[];
  trustEvidenceUrl?: string | null;
}

export const COURSE_TRUST_SIGNALS = [
  "nita_accredited",
  "university_backed",
  "free_open_access",
  "industry_certification",
] as const;

export type CourseTrustSignal = typeof COURSE_TRUST_SIGNALS[number];

export const COURSE_TRUST_SIGNAL_LABELS: Record<CourseTrustSignal, string> = {
  nita_accredited: "NITA-accredited",
  university_backed: "University-backed",
  free_open_access: "Free/Open Access",
  industry_certification: "Industry Certification",
};

export interface Recommendation {
  id: string;
  skillAnalysisId: string;
  learningResourceId: string;
  relevanceScore: number;
}
export type TrackedCourseStatus = "not_started" | "in_progress" | "completed";

export interface TrackedCourse {
  id: string;
  profileId: string;
  title: string;
  provider: string;
  url?: string;
  status: TrackedCourseStatus;
  enrolledAt: string;   // ISO date
  deadline?: string;    // ISO date, optional — some courses are self-paced
  notes?: string;
}