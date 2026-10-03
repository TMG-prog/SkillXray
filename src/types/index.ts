export interface Profile {
  id: string;
  fullName: string;
  email: string;
}

export interface Resume {
  id: string;
  profileId: string;
  fileUrl: string;
  uploadedAt: string;
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

export interface SkillAnalysis {
  id: string;
  resumeId: string;
  jobRoleId: string;
  careerReadinessIndex: number;
  createdAt: string;
}

export interface SkillGap {
  id: string;
  skillAnalysisId: string;
  skillId: string;
  severity: number;
}

export interface LearningResource {
  id: string;
  title: string;
  provider: string;
  url: string;
}

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