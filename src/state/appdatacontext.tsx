import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { supabase } from "@/lib/supabase";
import { getAnalysisHistory, saveAnalysisHistory } from "@/services/analysisHistoryService";
import {
  addTrackedCourse, deleteTrackedCourse, listTrackedCourses, updateTrackedCourseStatus,
} from "@/services/coursetracker";
import type { CourseTrustSignal, TrackedCourse, TrackedCourseStatus } from "@/types";

export interface SkillGap {
  skill: string;
  severity: "high" | "medium" | "low";
  fill: number; // 0-1, how much of the skill is present
  evidenceSection?: string | null;
}

export interface AnalysisRequirement {
  skill: string;
  uri: string;
  weight: number;
  credit: number;
  frequency: number | null;
  reason?: string;
  evidence?: string;
  cv_evidence?: string;
  cv_highlight?: string;
  evidence_section?: string | null;
  gap_confidence?: number;
}

export interface AnalysisExtractedSkill {
  skill: string;
  uri: string;
  in_esco: boolean;
  mentions: number;
}

export interface AnalysisMarketInsights {
  highRoiGaps: Array<{
    skill: string;
    frequency: number | null;
    readinessGainPoints: number;
    evidence: string;
    hiringEvidence: string | null;
  }>;
  emergingSkills: Array<{
    uri: string;
    skill: string;
    history: number[];
    previousFrequency: number;
    currentFrequency: number;
    deltaPp: number;
    emergenceScore: number;
    status: "core" | "rising" | "stable" | "declining";
    escoUri?: string | null;
    isEsco?: boolean;
    recentCount?: number;
    baselineCount?: number;
    recentPostings?: number;
    baselinePostings?: number;
    firstSeen?: boolean;
    confidence?: "low" | "medium" | "high";
    evidence?: string;
    samplePostings?: Array<{ title: string; postedAt: string; publisher: string }>;
  }>;
  currentPostings: number;
  previousPostings: number;
  emergingRole: string;
  recentWindowDays?: number;
  baselineWindowDays?: number;
  recentWindowStart?: string;
  recentWindowEnd?: string;
  baselineWindowStart?: string;
  baselineWindowEnd?: string;
  minimumSkillSupport?: number;
  minimumRecentPostings?: number;
  minimumBaselinePostings?: number;
  trendDataSufficient?: boolean;
  highRoiNote: string;
  emergingNote: string;
}

export interface AnalysisHiringEvidence {
  sampleSize: number;
  postingCount: number;
  frequency: number | null;
  baselineFrequency: number | null;
  personalized: boolean;
  evidence: string;
}

export interface AnalysisLearningPlanStep {
  rank: number;
  skill: string;
  uri: string;
  marginalGainPoints: number;
  clusterGainPoints: number;
  prerequisites: string[];
  clusterSkills: string[];
  coveredBy: string | null;
  hiringEvidence: AnalysisHiringEvidence | null;
  resource: {
    title: string;
    provider: string;
    url: string;
    trustSignals?: CourseTrustSignal[];
    trustEvidenceUrl?: string | null;
  } | null;
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
  learningPlan?: AnalysisLearningPlanStep[];
  extractedSkills?: AnalysisExtractedSkill[];
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
  coursesLoading: boolean;
  coursesError: string | null;
  retryCourses: () => void;
  addCourse: (course: NewCourse) => Promise<void>;
  updateCourseStatus: (id: string, status: TrackedCourseStatus) => Promise<void>;
  deleteCourse: (id: string) => Promise<void>;
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
  const [coursesLoading, setCoursesLoading] = useState(true);
  const [coursesError, setCoursesError] = useState<string | null>(null);
  const [coursesReload, setCoursesReload] = useState(0);
  const activeUserId = useRef<string | null>(null);
  const coursesRevision = useRef(0);

  const updateAuthenticatedUser = useCallback((nextUserId: string | null) => {
    if (activeUserId.current !== nextUserId) {
      activeUserId.current = nextUserId;
      coursesRevision.current += 1;
      setUserId(nextUserId);
      setAnalysis(null);
      setCourses([]);
      setCoursesError(null);
      setCoursesLoading(true);
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
        setCoursesError("Couldn't identify the signed-in user for courses.");
      }
      updateAuthenticatedUser(data.session?.user.id ?? null);
    }).catch((error: unknown) => {
      if (!active) return;
      console.error("Could not load the signed-in user:", error);
      setHistoryError("Couldn't identify the signed-in user for analysis history.");
      setHistoryLoading(false);
      setCoursesError("Couldn't identify the signed-in user for courses.");
      setCoursesLoading(false);
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

  useEffect(() => {
    if (!authReady) return;
    let active = true;

    async function loadCourses() {
      if (!userId) {
        setCourses([]);
        setCoursesLoading(false);
        return;
      }

      setCoursesLoading(true);
      setCoursesError(null);
      try {
        let revision: number;
        let loaded: TrackedCourse[];
        do {
          revision = coursesRevision.current;
          loaded = await listTrackedCourses(userId);
          if (!active || activeUserId.current !== userId) return;
        } while (revision !== coursesRevision.current);
        setCourses(loaded);
      } catch (error) {
        if (!active || activeUserId.current !== userId) return;
        console.error("Could not load tracked courses:", error);
        setCoursesError("Couldn't load your courses. Check your connection and try again.");
      } finally {
        if (active && activeUserId.current === userId) setCoursesLoading(false);
      }
    }

    void loadCourses();
    return () => { active = false; };
  }, [authReady, userId, coursesReload]);

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

  const addCourse = useCallback(async (course: NewCourse) => {
    const ownerId = activeUserId.current;
    if (!ownerId) throw new Error("Please sign in to save a course.");
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const enrolledAt = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const saved = await addTrackedCourse({
      ...course, profileId: ownerId, status: course.status ?? "not_started", enrolledAt,
    });
    if (activeUserId.current !== ownerId) {
      throw new Error("Your account changed while saving. Check your courses in the original account.");
    }
    coursesRevision.current += 1;
    setCourses((prev) => [...prev.filter((item) => item.id !== saved.id), saved]);
  }, []);

  const updateCourseStatus = useCallback(async (id: string, status: TrackedCourseStatus) => {
    const ownerId = activeUserId.current;
    if (!ownerId) throw new Error("Please sign in to update a course.");
    await updateTrackedCourseStatus(ownerId, id, status);
    if (activeUserId.current !== ownerId) return;
    coursesRevision.current += 1;
    setCourses((prev) => prev.map((c) => (c.id === id ? { ...c, status } : c)));
  }, []);

  const deleteCourse = useCallback(async (id: string) => {
    const ownerId = activeUserId.current;
    if (!ownerId) throw new Error("Please sign in to delete a course.");
    await deleteTrackedCourse(ownerId, id);
    if (activeUserId.current !== ownerId) return;
    coursesRevision.current += 1;
    setCourses((prev) => prev.filter((c) => c.id !== id));
  }, []);

  const retryCourses = useCallback(() => setCoursesReload((value) => value + 1), []);

  const value = useMemo(
    () => ({
      analysis, analysisHistory, historyLoading, historyError,
      completeResumeUpload, showHistoricalAnalysis, courses, coursesLoading, coursesError,
      retryCourses, addCourse, updateCourseStatus, deleteCourse,
    }),
    [analysis, analysisHistory, historyLoading, historyError, completeResumeUpload, showHistoricalAnalysis,
      courses, coursesLoading, coursesError, retryCourses, addCourse, updateCourseStatus, deleteCourse]
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData() {
  const ctx = useContext(AppDataContext);
  if (!ctx) throw new Error("useAppData must be used within an AppDataProvider");
  return ctx;
}