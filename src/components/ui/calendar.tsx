import { useMemo, useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { brand } from "./brand";

interface Props {
  deadlineDates: string[]; // ISO date strings (yyyy-mm-dd) that should show a dot
  selectedDate: string | null;
  onSelectDate: (iso: string) => void;
}

const WEEKDAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];

function toISO(d: Date) {
  return d.toISOString().slice(0, 10);
}

export function MonthCalendar({ deadlineDates, selectedDate, onSelectDate }: Props) {
  const [cursor, setCursor] = useState(() => new Date());

  const deadlineSet = useMemo(() => new Set(deadlineDates), [deadlineDates]);
  const todayISO = toISO(new Date());

  const { weeks, monthLabel } = useMemo(() => {
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    const firstOfMonth = new Date(year, month, 1);
    const startOffset = firstOfMonth.getDay(); // 0 = Sunday
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    const cells: (Date | null)[] = [
      ...Array(startOffset).fill(null),
      ...Array.from({ length: daysInMonth }, (_, i) => new Date(year, month, i + 1)),
    ];
    while (cells.length % 7 !== 0) cells.push(null);

    const weeks: (Date | null)[][] = [];
    for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

    const monthLabel = firstOfMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" });
    return { weeks, monthLabel };
  }, [cursor]);

  return (
    <View>
      <View style={styles.headerRow}>
        <Pressable onPress={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} hitSlop={10}>
          <Text style={styles.nav}>‹</Text>
        </Pressable>
        <Text style={styles.monthLabel}>{monthLabel}</Text>
        <Pressable onPress={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} hitSlop={10}>
          <Text style={styles.nav}>›</Text>
        </Pressable>
      </View>

      <View style={styles.weekdayRow}>
        {WEEKDAY_LABELS.map((d, i) => (
          <Text key={i} style={styles.weekdayLabel}>{d}</Text>
        ))}
      </View>

      {weeks.map((week, wi) => (
        <View key={wi} style={styles.weekRow}>
          {week.map((date, di) => {
            if (!date) return <View key={di} style={styles.dayCell} />;
            const iso = toISO(date);
            const isToday = iso === todayISO;
            const isSelected = iso === selectedDate;
            const hasDeadline = deadlineSet.has(iso);

            return (
              <Pressable key={di} style={styles.dayCell} onPress={() => onSelectDate(iso)}>
                <View style={[styles.dayCircle, isSelected && styles.dayCircleSelected]}>
                  <Text
                    style={[
                      styles.dayText,
                      isToday && !isSelected && styles.dayTextToday,
                      isSelected && styles.dayTextSelected,
                    ]}
                  >
                    {date.getDate()}
                  </Text>
                </View>
                {hasDeadline && <View style={[styles.dot, isSelected && styles.dotSelected]} />}
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  nav: { fontSize: 22, color: brand.text, paddingHorizontal: 12 },
  monthLabel: { fontSize: 16, fontWeight: "600", color: brand.text },
  weekdayRow: { flexDirection: "row", marginBottom: 4 },
  weekdayLabel: { flex: 1, textAlign: "center", fontSize: 12, color: brand.muted },
  weekRow: { flexDirection: "row" },
  dayCell: { flex: 1, aspectRatio: 1, alignItems: "center", justifyContent: "center" },
  dayCircle: { width: 32, height: 32, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  dayCircleSelected: { backgroundColor: "#25D9D0" },
  dayText: { fontSize: 14, color: brand.text },
  dayTextToday: { color: "#25D9D0", fontWeight: "700" },
  dayTextSelected: { color: "#06201F", fontWeight: "700" },
  dot: { width: 4, height: 4, borderRadius: 2, backgroundColor: "#25D9D0", marginTop: 2 },
  dotSelected: { backgroundColor: "#06201F" },
});