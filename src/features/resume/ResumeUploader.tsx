import { useState } from "react";
import { View, Text, Pressable, StyleSheet, ActivityIndicator } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { supabase } from "@/lib/supabase";
import { uploadResume } from "@/services/Resumeservice";
import { requestResumeParsing } from "@/services/skillAnalysisService";
import { brand, SERIF } from "@/components/ui/brand";

type Stage = "idle" | "uploading" | "extracting" | "error";

export function ResumeUploader() {
  const router = useRouter();
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
    if (!fileUri || !fileName) {
      setStage("error");
      setErrorMessage("Choose a resume file first.");
      return;
    }

    setErrorMessage(null);
    setStage("uploading");

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const user = session?.user;
      if (!user) throw new Error("You need to be signed in to upload a resume.");

      const resume = await uploadResume({ uri: fileUri, name: fileName, mimeType }, user.id);

      // Parses the file, runs the skill extractor and saves the skills.
      setStage("extracting");
      await requestResumeParsing(resume.id);

      // The skill gap analyzer isn't built yet, so show the extracted skills instead.
      // When it is: poll with pollForAnalysis(resume.id), load getSkillGaps(...),
      // call completeResumeUpload(...) and go to "/(tabs)/analysis".
      router.replace({
        pathname: "/resume-skills",
        params: { resumeId: resume.id, fileName },
      });
    } catch (err: any) {
      console.error("[analyze] failed", err);
      setStage("error");
      setErrorMessage(err?.message || "Something went wrong reading your resume.");
    }
  }

  const busy = stage === "uploading" || stage === "extracting";

  return (
    <View style={{ padding: 20 }}>
      <Text style={{ fontFamily: SERIF, fontSize: 24, color: brand.text, marginBottom: 8 }}>
        Upload your resume
      </Text>
      <Text style={{ color: brand.muted, marginBottom: 20 }}>
        We'll extract your skills and compare them against your target role.
      </Text>

      <View style={styles.dropzone}>
        <Feather name="upload-cloud" size={28} color={brand.muted} />
        <Text style={{ color: brand.muted, marginTop: 8 }}>{fileName ?? "PDF or Word (.docx) document"}</Text>
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
          stage === "uploading" ? "Uploading…" : stage === "extracting" ? "Extracting skills…" : "Extract my skills"
        }
        disabled={!fileName || busy}
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