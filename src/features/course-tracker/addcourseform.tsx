import { useRef, useState } from "react";
import {
  View,
  Text,
  TextInput,
  Pressable,
  ScrollView,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { brand, colors, SERIF } from "@/components/ui/theme";
import { MonthCalendar } from "@/components/ui/calendar";
import { useAppData } from "@/state/appdatacontext";
import type { TrackedCourse } from "@/types";

type Status = TrackedCourse["status"];

const STATUS_OPTIONS: { value: Status; label: string }[] = [
  { value: "not_started", label: "Not started" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
];

const formatDate = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

export function AddCourseForm() {
  const router = useRouter();
  const { addCourse } = useAppData();

  const [title, setTitle] = useState("");
  const [provider, setProvider] = useState("");
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<Status>("in_progress");
  const [deadline, setDeadline] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);

  async function handleSave() {
    if (savingRef.current) return;
    if (!title.trim()) {
      setError("Add a course title.");
      return;
    }

    const trimmedUrl = url.trim();
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      await addCourse({
        title: title.trim(),
        provider: provider.trim(),
        status,
        deadline: deadline ?? undefined,
        url: trimmedUrl
          ? /^https?:\/\//i.test(trimmedUrl)
            ? trimmedUrl
            : `https://${trimmedUrl}`
          : undefined,
      });
      router.back();
    } catch (err) {
      console.error("Could not save tracked course:", err);
      setError(err instanceof Error ? err.message : "Couldn't save your course. Check your connection and try again.");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} disabled={saving} hitSlop={12} accessibilityLabel="Go back">
            <Feather name="chevron-left" size={28} color={brand.text} />
          </Pressable>
          <Text style={styles.title}>Add course</Text>
        </View>
        <Text style={styles.subtitle}>
          Add a course you've signed up for elsewhere so its deadline stays in view.
        </Text>

        <Text style={styles.label}>Course title</Text>
        <TextInput
          value={title}
          onChangeText={(t) => {
            setTitle(t);
            if (error) setError(null);
          }}
          placeholder="e.g. Python for Data Analysis"
          placeholderTextColor={brand.muted}
          style={styles.input}
          returnKeyType="next"
        />

        <Text style={styles.label}>Platform or provider</Text>
        <TextInput
          value={provider}
          onChangeText={setProvider}
          placeholder="e.g. Coursera"
          placeholderTextColor={brand.muted}
          style={styles.input}
          returnKeyType="next"
        />

        <Text style={styles.label}>Course link (optional)</Text>
        <TextInput
          value={url}
          onChangeText={setUrl}
          placeholder="https://"
          placeholderTextColor={brand.muted}
          style={styles.input}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />

        <Text style={styles.label}>Status</Text>
        <View style={styles.chipRow}>
          {STATUS_OPTIONS.map((opt) => {
            const active = status === opt.value;
            return (
              <Pressable
                key={opt.value}
                onPress={() => setStatus(opt.value)}
                style={[styles.chip, active && styles.chipActive]}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>
                  {opt.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <View style={styles.deadlineHeader}>
          <Text style={styles.label}>Deadline (optional)</Text>
          {deadline && (
            <Pressable onPress={() => setDeadline(null)} hitSlop={8}>
              <Text style={styles.clear}>Clear</Text>
            </Pressable>
          )}
        </View>
        <Text style={styles.deadlineValue}>
          {deadline ? formatDate(deadline) : "Tap a day on the calendar to set one"}
        </Text>
        <View style={styles.calendarCard}>
          <MonthCalendar
            deadlineDates={[]}
            selectedDate={deadline}
            onSelectDate={(iso) => setDeadline(iso)}
          />
        </View>

        {error && <Text style={styles.error}>{error}</Text>}

        <Pressable
          onPress={handleSave}
          style={styles.saveButton}
          accessibilityRole="button"
          accessibilityState={{ disabled: saving, busy: saving }}
          disabled={saving}
        >
          <Text style={styles.saveButtonText}>{saving ? "Saving..." : "Save course"}</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, paddingBottom: 48 },
  headerRow: { flexDirection: "row", alignItems: "center", gap: 4, marginLeft: -6 },
  title: { fontFamily: SERIF, fontSize: 28, color: brand.text, letterSpacing: -0.5 },
  subtitle: { fontSize: 15, lineHeight: 21, color: brand.muted, marginTop: 8, marginBottom: 12 },
  label: { fontSize: 13, fontWeight: "600", color: brand.muted, marginTop: 16, marginBottom: 6 },
  input: {
    backgroundColor: brand.surfaceSolid,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 12,
    color: brand.text,
    fontSize: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: brand.border,
    paddingVertical: 8,
    paddingHorizontal: 14,
  },
  chipActive: { backgroundColor: brand.cyan, borderColor: brand.cyan },
  chipText: { color: brand.text, fontSize: 14, fontWeight: "600" },
  chipTextActive: { color: brand.onGradient },
  deadlineHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end" },
  clear: { fontSize: 14, color: brand.cyan, marginBottom: 6 },
  deadlineValue: { fontSize: 15, color: brand.text, marginBottom: 10 },
  calendarCard: {
    backgroundColor: brand.surfaceSolid,
    borderRadius: 16,
    padding: 16,
  },
  error: { color: colors.dark.severityHigh, fontSize: 13, marginTop: 16 },
  saveButton: {
    backgroundColor: brand.cyan,
    borderRadius: 999,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 24,
  },
  saveButtonText: { color: brand.onGradient, fontWeight: "700", fontSize: 16 },
});