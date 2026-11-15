import { useState } from "react";
import { View, Text, Pressable, StyleSheet, ActivityIndicator } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { supabase } from "@/lib/supabase";
import { uploadResume } from "@/services/Resumeservice";
import { analyzeResumeFile, USE_MOCK_ANALYSIS } from "@/services/skillAnalysisService";
import { useAppData } from "@/state/appdatacontext";
import { brand, SERIF } from "@/components/ui/theme";

type Stage = "idle" | "uploading" | "analyzing" | "error";

export function ResumeUploader() {
  const router = useRouter();
  const { completeResumeUpload } = useAppData();
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileUri, setFileUri] = useState<string | null>(null);
  const [mimeType, setMimeType] = useState<string | undefined>();
  const [stage, setStage] = useState<Stage>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function pickResume() {
    const result = await DocumentPicker.getDocumentAsync({
      // The parser reads PDF and .docx (not the old .doc format).
      type: [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ],
    });
    if (result.canceled) return;
    const asset = result.assets[0];
    setFileName(asset.name);
    setFileUri(asset.uri);
    setMimeType(asset.mimeType);
    setErrorMessage(null);
  }

  async function handleAnalyze() {
    if (!USE_MOCK_ANALYSIS && (!fileUri || !fileName)) {
      setStage("error");
      setErrorMessage("Choose a resume file first.");
      return;
    }

    setErrorMessage(null);
    setStage(USE_MOCK_ANALYSIS ? "analyzing" : "uploading");

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const user = session?.user;
      if (!user) throw new Error("You need to be signed in to upload a resume.");

      const { data: profile, error: profileError } = await supabase
        .from("profiles")
        .select("target_role")
        .eq("id", user.id)
        .maybeSingle();
      if (profileError) throw profileError;
      const targetRole = profile?.target_role?.trim();
      if (!targetRole) throw new Error("Choose a target role before analyzing your resume.");

      let resumeId: string | null = null;
      if (!USE_MOCK_ANALYSIS) {
        if (!fileUri || !fileName) throw new Error("Choose a resume file first.");
        const resume = await uploadResume({ uri: fileUri, name: fileName, mimeType }, user.id);
        resumeId = resume.id;
      }

      setStage("analyzing");
      const result = await analyzeResumeFile({
        uri: fileUri ?? "",
        name: fileName ?? "Demo resume",
        mimeType,
      }, targetRole);
      const mostImportantGapCount = Math.ceil(result.gaps.length / 3);
      const mediumGapCount = Math.ceil((result.gaps.length * 2) / 3);
      await completeResumeUpload({
        demo: result.demo === true,
        resumeFileName: fileName ?? "Demo resume",
        targetRole: result.role,
        readiness: result.readiness,
        covered: result.covered.map((item) => item.skill),
        requirements: [...result.covered, ...result.gaps],
        extractedSkills: result.extracted_skills,
        relationships: result.skill_relationships,
        marketInsights: {
          highRoiGaps: result.market_delta.high_roi_gaps.map((gap) => ({
            skill: gap.skill,
            frequency: gap.frequency,
            readinessGainPoints: gap.readiness_gain_pp,
            evidence: gap.evidence,
          })),
          emergingSkills: result.market_emergence?.skills.map((skill) => ({
            uri: skill.esco_uri,
            skill: skill.skill,
            history: skill.history,
            previousFrequency: skill.previous_frequency,
            currentFrequency: skill.current_frequency,
            deltaPp: skill.delta_pp,
            emergenceScore: skill.emergence_score,
            status: skill.status,
          })) ?? [],
          currentPostings: result.market_emergence?.current_postings ?? 0,
          previousPostings: result.market_emergence?.previous_postings ?? 0,
          emergingRole: result.market_emergence?.role ?? result.role,
          highRoiNote: result.market_delta.high_roi_note,
          emergingNote: result.market_delta.emerging_note,
        },
        warnings: result.warnings,
        gaps: result.gaps.map((gap, index) => ({
          skill: gap.skill,
          severity: index < mostImportantGapCount ? "high" : index < mediumGapCount ? "medium" : "low",
          fill: gap.credit,
        })),
      }, user.id, resumeId, targetRole);
      router.replace({
        pathname: "/(tabs)/analysis",
      });
    } catch (err) {
      console.error("[analyze] failed", err);
      setStage("error");
      setErrorMessage(err instanceof Error ? err.message : "Something went wrong reading your resume.");
    }
  }

  const busy = stage === "uploading" || stage === "analyzing";

  return (
    <View style={{ padding: 20 }}>
      <Text style={{ fontFamily: SERIF, fontSize: 24, color: brand.text, marginBottom: 8 }}>
        Upload your resume
      </Text>
      <Text style={{ color: brand.muted, marginBottom: 20 }}>
        {USE_MOCK_ANALYSIS
          ? "Demo mode is on. Sample results will be shown without uploading your resume or contacting the analysis model."
          : "We'll extract your skills and compare them against your target role."}
      </Text>

      <View style={styles.dropzone}>
        <Feather name="upload-cloud" size={28} color={brand.muted} />
        <Text style={{ color: brand.muted, marginTop: 8 }}>
          {fileName ?? (USE_MOCK_ANALYSIS ? "Resume optional in demo mode" : "PDF or Word (.docx) document")}
        </Text>
        <TrackerButton
          onPress={pickResume}
          label={fileName ? "Choose a different file" : "Choose file"}
          disabled={busy}
        />
      </View>

      {errorMessage && <Text style={styles.errorText}>{errorMessage}</Text>}

      <TrackerButton
        onPress={handleAnalyze}
        label={
          stage === "uploading" ? "Uploading…"
            : stage === "analyzing" ? (USE_MOCK_ANALYSIS ? "Generating demo…" : "Analyzing resume…")
              : USE_MOCK_ANALYSIS ? "Generate demo analysis" : "Analyze my resume"
        }
        disabled={(!fileName && !USE_MOCK_ANALYSIS) || busy}
        solid
        loading={busy}
      />
    </View>
  );
}

function TrackerButton({
  onPress,
  label,
  disabled,
  solid,
  loading,
}: {
  onPress: () => void;
  label: string;
  disabled?: boolean;
  solid?: boolean;
  loading?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={{
        marginTop: 16,
        backgroundColor: solid ? "#25D9D0" : "rgba(255,255,255,0.08)",
        borderRadius: 999,
        paddingVertical: 12,
        paddingHorizontal: 20,
        alignItems: "center",
        flexDirection: "row",
        justifyContent: "center",
        gap: 8,
        opacity: disabled ? 0.4 : 1,
      }}
    >
      {loading && <ActivityIndicator size="small" color={solid ? "#06201F" : brand.text} />}
      <Text style={{ color: solid ? "#06201F" : brand.text, fontWeight: "700" }}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  dropzone: {
    alignItems: "center",
    paddingVertical: 32,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: "rgba(255,255,255,0.15)",
    borderRadius: 16,
  },
  errorText: { color: "#F87171", marginTop: 12, fontSize: 13 },
});