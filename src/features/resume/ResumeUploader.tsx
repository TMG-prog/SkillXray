import { useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { useAppData } from "@/state/appdatacontext";
import { brand, SERIF } from "@/components/ui/brand";

export function ResumeUploader() {
  const router = useRouter();
  const { completeResumeUpload } = useAppData();
  const [fileName, setFileName] = useState<string | null>(null);

  async function pickResume() {
    const result = await DocumentPicker.getDocumentAsync({
      type: [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ],
    });
    if (result.canceled) return;
    setFileName(result.assets[0].name);
  }

  function handleAnalyze() {
    if (!fileName) return;
    completeResumeUpload(fileName); // TODO: replace with real upload + analysis call
    router.replace("/(tabs)/analysis");
  }

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
        <Text style={{ color: brand.muted, marginTop: 8 }}>{fileName ?? "PDF or Word document"}</Text>
        <TrackerButton onPress={pickResume} label={fileName ? "Choose a different file" : "Choose file"} />
      </View>

      <TrackerButton onPress={handleAnalyze} label="Analyze my resume" disabled={!fileName} solid />
    </View>
  );
}

function TrackerButton({
  onPress,
  label,
  disabled,
  solid,
}: {
  onPress: () => void;
  label: string;
  disabled?: boolean;
  solid?: boolean;
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
        opacity: disabled ? 0.4 : 1,
      }}
    >
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
});