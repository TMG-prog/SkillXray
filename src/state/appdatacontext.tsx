import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { supabase } from "@/lib/supabase";
import { getAnalysisHistory, saveAnalysisHistory } from "@/services/analysisHistoryService";
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

export interface AnalysisRequirement {
  skill: string;
  uri: string;
  weight: number;
  credit: number;
  frequency: number | null;
  reason?: string;
  evidence?: string;
  gap_confidence?: number;
}

export interface AnalysisMarketInsights {
  highRoiGaps: Array<{
    skill: string;
    frequency: number | null;
    readinessGainPoints: number;
    evidence: string;
  }>;
  highRoiNote: string;
  emergingNote: string;
}

export interface AnalysisSkillRelationship {
  source: string;
  target: string;
  type: "prerequisite" | "broader" | "related";
}

export interface Analysis {
  demo: boolean;
  resumeFileName: string;
  targetRole: string;
  readiness: number; // 0-100
  gaps: SkillGap[];
  covered: string[];
  requirements: AnalysisRequirement[];
  relationships: AnalysisSkillRelationship[];
  marketInsights: AnalysisMarketInsights;
  warnings: string[];
}

export interface AnalysisHistoryEntry {
  id: string;
  createdAt: string;
  analysis: Analysis;
}

type NewCourse = Omit<TrackedCourse, "id" | "profileId" | "enrolledAt" | "status"> & {
  status?: TrackedCourseStatus;
};

interface AppDataContextValue {
  analysis: Analysis | null;
  analysisHistory: AnalysisHistoryEntry[];
  historyLoading: boolean;
  historyError: string | null;
  completeResumeUpload: (
    analysis: Analysis,
    userId: string,
    resumeId: string | null,
    roleTitle: string,
  ) => Promise<void>;
  showHistoricalAnalysis: (entry: AnalysisHistoryEntry) => void;
  courses: TrackedCourse[];
  addCourse: (course: NewCourse) => void;  updateCourseStatus: (id: string, status: TrackedCourseStatus) => void;
  deleteCourse: (id: string) => void;
}

const AppDataContext = createContext<AppDataContextValue | null>(null);

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [courses, setCourses] = useState<TrackedCourse[]>([]);
  const activeUserId = useRef<string | null>(null);

  const updateAuthenticatedUser = useCallback((nextUserId: string | null) => {
    if (activeUserId.current !== nextUserId) {
      activeUserId.current = nextUserId;
      setUserId(nextUserId);
      setAnalysis(null);
    }
    setAuthReady(true);
  }, []);

  useEffect(() => {
    let active = true;
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!active) return;
      updateAuthenticatedUser(session?.user.id ?? null);
    });

    supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return;
      if (error) {
        setHistoryError("Couldn't identify the signed-in user for analysis history.");
        setHistoryLoading(false);
      }
      updateAuthenticatedUser(data.session?.user.id ?? null);
    }).catch((error: unknown) => {
      if (!active) return;
      console.error("Could not load the signed-in user:", error);
      setHistoryError("Couldn't identify the signed-in user for analysis history.");
      setHistoryLoading(false);
      setAuthReady(true);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [updateAuthenticatedUser]);

  useEffect(() => {
    if (!authReady) return;
    let active = true;

    async function loadHistory() {
      setHistoryLoading(true);
      setHistoryError(null);
      setAnalysisHistory([]);
      if (!userId) {
        setAnalysis(null);
        setHistoryLoading(false);
        return;
      }

      try {
        const entries = await getAnalysisHistory(userId);
        if (!active) return;
        setAnalysisHistory(entries);
        setAnalysis(entries[0]?.analysis ?? null);
      } catch (error) {
        if (!active) return;
        console.error("Could not load analysis history:", error);
        setHistoryError("Couldn't load saved analyses from your account.");
        setAnalysis(null);
      } finally {
        if (active) setHistoryLoading(false);
      }
    }

    void loadHistory();
    return () => { active = false; };
  }, [authReady, userId]);

  const completeResumeUpload = useCallback(async (
    nextAnalysis: Analysis,
    ownerId: string,
    resumeId: string | null,
    roleTitle: string,
  ) => {
    if (resumeId) {
      const entry = await saveAnalysisHistory(nextAnalysis, ownerId, resumeId, roleTitle);
      setAnalysisHistory((previous) => [entry, ...previous.filter((item) => item.id !== entry.id)].slice(0, 50));
    }
    setHistoryError(null);
    setAnalysis(nextAnalysis);
  }, []);

  const showHistoricalAnalysis = useCallback((entry: AnalysisHistoryEntry) => {
    setAnalysis(entry.analysis);
  }, []);

 function addCourse(course: NewCourse) {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const today = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

  setCourses((prev) => [
    ...prev,
    {
      ...course,
      id: String(Date.now()),
      profileId: "me",
      status: course.status ?? "not_started",
      enrolledAt: today,
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
    () => ({
      analysis, analysisHistory, historyLoading, historyError,
      completeResumeUpload, showHistoricalAnalysis, courses, addCourse, updateCourseStatus, deleteCourse,
    }),
    [analysis, analysisHistory, historyLoading, historyError, completeResumeUpload, showHistoricalAnalysis, courses]
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData() {
  const ctx = useContext(AppDataContext);
  if (!ctx) throw new Error("useAppData must be used within an AppDataProvider");
  return ctx;
}