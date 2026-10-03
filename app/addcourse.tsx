import { useState } from "react";
import { View, Text, TextInput, StyleSheet, Pressable, ScrollView } from "react-native";
import { useRouter } from "expo-router";
import { brand, SERIF } from "@/components/ui/brand";

// TODO: wire to addTrackedCourse() from services/trackedCoursesService.ts
export default function AddCourseScreen() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [provider, setProvider] = useState("");
  const [url, setUrl] = useState("");
  const [deadline, setDeadline] = useState(""); // yyyy-mm-dd

  const canSave = title.trim().length > 0;

  function handleSave() {
    // TODO: await addTrackedCourse({ ...fields, status: "not_started", enrolledAt: todayISO })
    router.back();
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: brand.bg }} contentContainerStyle={styles.container}>
      <Text style={styles.title}>Add a course</Text>

      <Field label="Course title *" value={title} onChangeText={setTitle} placeholder="Python for Data Analysis" />
      <Field label="Provider" value={provider} onChangeText={setProvider} placeholder="Coursera, edX, Udemy…" />
      <Field label="Link" value={url} onChangeText={setUrl} placeholder="https://…" autoCapitalize="none" />
      <Field label="Deadline" value={deadline} onChangeText={setDeadline} placeholder="YYYY-MM-DD" />

      <Pressable
        style={[styles.saveButton, !canSave && { opacity: 0.4 }]}
        disabled={!canSave}
        onPress={handleSave}
      >
        <Text style={styles.saveButtonText}>Save course</Text>
      </Pressable>
    </ScrollView>
  );
}

function Field(props: { label: string; value: string; onChangeText: (t: string) => void; placeholder?: string; autoCapitalize?: "none" | "sentences" }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{props.label}</Text>
      <TextInput
        style={styles.input}
        value={props.value}
        onChangeText={props.onChangeText}
        placeholder={props.placeholder}
        placeholderTextColor={brand.muted}
        autoCapitalize={props.autoCapitalize}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20, paddingBottom: 40 },
  title: { fontFamily: SERIF, fontSize: 26, color: brand.text, marginBottom: 20 },
  field: { marginBottom: 16 },
  label: { fontSize: 13, color: brand.muted, marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: brand.text,
    fontSize: 15,
  },
  saveButton: {
    backgroundColor: "#25D9D0",
    borderRadius: 999,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 12,
  },
  saveButtonText: { color: "#06201F", fontWeight: "700", fontSize: 15 },
});