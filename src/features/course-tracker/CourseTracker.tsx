import { useMemo, useState } from "react";
import { View, Text, StyleSheet, Pressable, FlatList, Linking } from "react-native";
import { useRouter } from "expo-router";
import { brand, SERIF } from "@/components/ui/brand";
import { MonthCalendar } from "@/components/ui/calendar";
import { StatusBadge } from "@/components/ui/statusbadge";
import type { TrackedCourse } from "@/types";

// TODO: replace with listTrackedCourses(profileId) from
// services/trackedCoursesService.ts once auth + Supabase wiring is in.
const MOCK_COURSES: TrackedCourse[] = [
  {
    id: "1",
    profileId: "me",
    title: "Python for Data Analysis",
    provider: "Coursera",
    status: "in_progress",
    enrolledAt: "2026-09-01",
    deadline: "2026-10-15",
  },
  {
    id: "2",
    profileId: "me",
    title: "Project Management Basics",
    provider: "edX",
    status: "not_started",
    enrolledAt: "2026-09-20",
    deadline: "2026-10-05",
  },
  {
    id: "3",
    profileId: "me",
    title: "Advanced Data Analysis",
    provider: "Udemy",
    status: "completed",
    enrolledAt: "2026-07-01",
  },
];

export function CourseTracker() {
  const router = useRouter();
  const [courses] = useState<TrackedCourse[]>(MOCK_COURSES);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const deadlineDates = useMemo(
    () => courses.filter((c) => c.deadline).map((c) => c.deadline!),
    [courses]
  );

  const visibleCourses = useMemo(() => {
    if (!selectedDate) return courses;
    return courses.filter((c) => c.deadline === selectedDate);
  }, [courses, selectedDate]);

  const upcoming = useMemo(() => {
    const todayISO = new Date().toISOString().slice(0, 10);
    return courses
      .filter((c) => c.deadline && c.deadline >= todayISO && c.status !== "completed")
      .sort((a, b) => (a.deadline! < b.deadline! ? -1 : 1))
      .slice(0, 1)[0];
  }, [courses]);

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>My Courses</Text>
        <Pressable style={styles.addButton} onPress={() => router.push("/add-course")}>
          <Text style={styles.addButtonText}>+ Add</Text>
        </Pressable>
      </View>
      <Text style={styles.subtitle}>
        Track the courses you've signed up for elsewhere, and keep an eye on deadlines.
      </Text>

      {upcoming && (
        <View style={styles.nextDeadlineCard}>
          <Text style={styles.nextDeadlineLabel}>Next deadline</Text>
          <Text style={styles.nextDeadlineTitle}>{upcoming.title}</Text>
          <Text style={styles.nextDeadlineDate}>
            Due {new Date(upcoming.deadline!).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
          </Text>
        </View>
      )}

      <View style={styles.calendarCard}>
        <MonthCalendar
          deadlineDates={deadlineDates}
          selectedDate={selectedDate}
          onSelectDate={(iso) => setSelectedDate((prev) => (prev === iso ? null : iso))}
        />
      </View>

      <View style={styles.listHeaderRow}>
        <Text style={styles.listHeader}>
          {selectedDate ? "Due this day" : "All courses"}
        </Text>
        {selectedDate && (
          <Pressable onPress={() => setSelectedDate(null)}>
            <Text style={styles.clearFilter}>Clear</Text>
          </Pressable>
        )}
      </View>

      <FlatList
        data={visibleCourses}
        keyExtractor={(c) => c.id}
        scrollEnabled={false}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        renderItem={({ item }) => (
          <Pressable
            style={styles.courseRow}
            onPress={() => item.url && Linking.openURL(item.url)}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.courseTitle}>{item.title}</Text>
              <Text style={styles.courseProvider}>{item.provider}</Text>
              <View style={{ marginTop: 8 }}>
                <StatusBadge status={item.status} />
              </View>
            </View>
            {item.deadline && (
              <Text style={styles.courseDeadline}>
                {new Date(item.deadline).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              </Text>
            )}
          </Pressable>
        )}
        ListEmptyComponent={
          <Text style={styles.emptyText}>Nothing due this day.</Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, paddingBottom: 40 },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { fontFamily: SERIF, fontSize: 28, color: brand.text, letterSpacing: -0.5 },
  subtitle: { fontSize: 15, lineHeight: 21, color: brand.muted, marginTop: 8, marginBottom: 20 },
  addButton: {
    backgroundColor: "#25D9D0",
    borderRadius: 999,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  addButtonText: { color: "#06201F", fontWeight: "700", fontSize: 14 },
  nextDeadlineCard: {
    backgroundColor: "rgba(37,217,208,0.12)",
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
  },
  nextDeadlineLabel: { fontSize: 12, color: "#25D9D0", fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5 },
  nextDeadlineTitle: { fontSize: 17, fontWeight: "600", color: brand.text, marginTop: 4 },
  nextDeadlineDate: { fontSize: 14, color: brand.muted, marginTop: 2 },
  calendarCard: { backgroundColor: "rgba(255,255,255,0.03)", borderRadius: 16, padding: 16, marginBottom: 24 },
  listHeaderRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  listHeader: { fontSize: 15, fontWeight: "700", color: brand.text },
  clearFilter: { fontSize: 14, color: "#25D9D0" },
  separator: { height: 1, backgroundColor: "rgba(255,255,255,0.08)", marginVertical: 12 },
  courseRow: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between" },
  courseTitle: { fontSize: 16, fontWeight: "600", color: brand.text },
  courseProvider: { fontSize: 13, color: brand.muted, marginTop: 2 },
  courseDeadline: { fontSize: 13, color: brand.muted, marginLeft: 12 },
  emptyText: { fontSize: 14, color: brand.muted, textAlign: "center", paddingVertical: 20 },
});