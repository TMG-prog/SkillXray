import { useMemo, useState } from "react";
import { View, Text, StyleSheet, Pressable, FlatList, Linking } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { brand, SERIF } from "@/components/ui/theme";
import { MonthCalendar } from "@/components/ui/calendar";
import { StatusBadge } from "@/components/ui/statusbadge";
import { useAppData } from "@/state/appdatacontext";
import { useSafeAreaInsets } from "react-native-safe-area-context";

export function CourseTracker() {
  const router = useRouter();
  const { courses } = useAppData();
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const insets = useSafeAreaInsets();
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

  if (courses.length === 0) {
    return (
      <View style={styles.container}>
        <View style={styles.headerRow}>
          <Text style={styles.title}>My Courses</Text>
          <Pressable style={styles.addButtonWrap} onPress={() => router.push("/add-course")}>
            <LinearGradient colors={[brand.cyan, brand.mint]} style={styles.addButton}>
              <Text style={styles.addButtonText}>+ Add</Text>
            </LinearGradient>
          </Pressable>
        </View>
        <Text style={styles.subtitle}>
          Track the courses you've signed up for elsewhere, and keep an eye on deadlines.
        </Text>

        <View style={styles.emptyState}>
          <View style={styles.emptyIconCircle}>
            <Feather name="calendar" size={24} color={brand.cyan} />
          </View>
          <Text style={styles.emptyTitle}>No courses tracked yet</Text>
          <Text style={styles.emptyMessage}>
            Add a course you've signed up for elsewhere to keep its deadline in view.
          </Text>
          <Pressable style={styles.emptyButtonWrap} onPress={() => router.push("/add-course")}>
            <LinearGradient colors={[brand.cyan, brand.mint]} style={styles.emptyButton}>
              <Text style={styles.emptyButtonText}>Add your first course</Text>
            </LinearGradient>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>My Courses</Text>
        <Pressable style={styles.addButtonWrap} onPress={() => router.push("/add-course")}>
          <LinearGradient colors={[brand.cyan, brand.mint]} style={styles.addButton}>
            <Text style={styles.addButtonText}>+ Add</Text>
          </LinearGradient>
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
  addButtonWrap: { borderRadius: 999, overflow: "hidden" },
  addButton: {
    borderRadius: 999,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  addButtonText: { color: brand.onGradient, fontWeight: "700", fontSize: 14 },
  nextDeadlineCard: {
    backgroundColor: brand.tint,
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
  },
  nextDeadlineLabel: { fontSize: 12, color: brand.cyan, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5 },
  nextDeadlineTitle: { fontSize: 17, fontWeight: "600", color: brand.text, marginTop: 4 },
  nextDeadlineDate: { fontSize: 14, color: brand.muted, marginTop: 2 },
  calendarCard: { backgroundColor: brand.surface, borderRadius: 16, padding: 16, marginBottom: 24 },
  listHeaderRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  listHeader: { fontSize: 15, fontWeight: "700", color: brand.text },
  clearFilter: { fontSize: 14, color: brand.cyan },
  separator: { height: 1, backgroundColor: brand.border, marginVertical: 12 },
  courseRow: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between" },
  courseTitle: { fontSize: 16, fontWeight: "600", color: brand.text },
  courseProvider: { fontSize: 13, color: brand.muted, marginTop: 2 },
  courseDeadline: { fontSize: 13, color: brand.muted, marginLeft: 12 },
  emptyText: { fontSize: 14, color: brand.muted, textAlign: "center", paddingVertical: 20 },
  emptyState: { alignItems: "center", paddingVertical: 48, paddingHorizontal: 16 },
  emptyIconCircle: {
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: brand.tint,
    alignItems: "center", justifyContent: "center", marginBottom: 16,
  },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: brand.text, marginBottom: 6 },
  emptyMessage: { fontSize: 14, color: brand.muted, textAlign: "center", marginBottom: 20, lineHeight: 20 },
  emptyButtonWrap: { borderRadius: 999, overflow: "hidden" },
  emptyButton: { borderRadius: 999, paddingVertical: 12, paddingHorizontal: 24 },
  emptyButtonText: { color: brand.onGradient, fontWeight: "700", fontSize: 14 },
});