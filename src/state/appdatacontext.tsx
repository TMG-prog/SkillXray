import { createContext, useContext, useMemo, useState, ReactNode } from "react";
import type { TrackedCourse, TrackedCourseStatus } from "@/types";

// TODO: this whole file is a stand-in for real Supabase-backed state. Once
// auth + data fetching are wired up, replace the useState calls with
// React Query (or similar) reads from SkillAnalyses / SkillGaps / TrackedCourses,
// and the action functions with the corresponding inserts/updates.

export interface SkillGap {
  skill: string;
  severity: "high" | "medium" | "low";
  fill: number; // 0-1, how much of the skill is present
}

export interface Analysis {
  resumeFileName: string;
  readiness: number; // 0-100
  gaps: SkillGap[];
}

interface AppDataContextValue {
  analysis: Analysis | null;
  completeResumeUpload: (fileName: string) => void;
  courses: TrackedCourse[];
  addCourse: (course: Omit<TrackedCourse, "id" | "profileId" | "enrolledAt" | "status">) => void;
  updateCourseStatus: (id: string, status: TrackedCourseStatus) => void;
  deleteCourse: (id: string) => void;
}

const AppDataContext = createContext<AppDataContextValue | null>(null);

// Mock gap output — stands in for what the NLP/Skill Gap Analyzer would
// actually return once the backend pipeline exists.
const MOCK_ANALYSIS_RESULT: Omit<Analysis, "resumeFileName"> = {
  readiness: 65,
  gaps: [
    { skill: "Python", severity: "high", fill: 0.35 },
    { skill: "Data Analysis", severity: "medium", fill: 0.55 },
    { skill: "Project management", severity: "medium", fill: 0.55 },
  ],
};

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [courses, setCourses] = useState<TrackedCourse[]>([]);

  function completeResumeUpload(fileName: string) {
    setAnalysis({ resumeFileName: fileName, ...MOCK_ANALYSIS_RESULT });
  }

  function addCourse(course: Omit<TrackedCourse, "id" | "profileId" | "enrolledAt" | "status">) {
    setCourses((prev) => [
      ...prev,
      {
        ...course,
        id: String(Date.now()),
        profileId: "me",
        status: "not_started",
        enrolledAt: new Date().toISOString().slice(0, 10),
      },
    ]);
  }

  function updateCourseStatus(id: string, status: TrackedCourseStatus) {
    setCourses((prev) => prev.map((c) => (c.id === id ? { ...c, status } : c)));
  }

  function deleteCourse(id: string) {
    setCourses((prev) => prev.filter((c) => c.id !== id));
  }

  const value = useMemo(
    () => ({ analysis, completeResumeUpload, courses, addCourse, updateCourseStatus, deleteCourse }),
    [analysis, courses]
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData() {
  const ctx = useContext(AppDataContext);
  if (!ctx) throw new Error("useAppData must be used within an AppDataProvider");
  return ctx;
}