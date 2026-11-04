import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Feather } from "@expo/vector-icons";
import { supabase } from "@/lib/supabase";
import { getSupportedRoles, USE_MOCK_ANALYSIS } from "@/services/skillAnalysisService";
import { brand, spacing } from "@/components/ui/theme";

export type JobRole = {
  id: string;
  title: string;
  description: string | null;
};

// ESCO titles are lowercase ("software developer"); show them with a capital.
export const formatRole = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const RESULT_LIMIT = 40;

type Props = {
  /** Currently selected role title (the value stored in profiles.target_role) */
  value: string | null;
  onSelect: (role: JobRole) => void;
  disabled?: boolean;
};

export default function RolePicker({ value, onSelect, disabled }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<JobRole[]>([]);
  const [supportedRoles, setSupportedRoles] = useState<JobRole[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0); // ignore out-of-order responses

  const search = useCallback(async (text: string) => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);

    const term = text.trim().replace(/[%_\\]/g, (m) => "\\" + m); // escape LIKE wildcards
    const { data, error: err } = await supabase
      .from("job_roles")
      .select("id, title, description")
      .ilike("title", term ? `%${term}%` : "%")
      .order("title", { ascending: true })
      .limit(RESULT_LIMIT);
    if (id !== requestId.current) return; // a newer search has started

    if (err) {
      console.error("Role search failed:", err);
      setError("Couldn't load roles. Check your connection and try again.");
      setResults([]);
    } else {
      const lower = text.trim().toLowerCase();
      // Put titles that START with the query first, then the rest alphabetically
      const sorted = [...(data ?? [])].sort((a, b) => {
        const aStarts = lower && a.title.toLowerCase().startsWith(lower) ? 0 : 1;
        const bStarts = lower && b.title.toLowerCase().startsWith(lower) ? 0 : 1;
        return aStarts - bStarts || a.title.localeCompare(b.title);
      });
      setResults(sorted);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!open || USE_MOCK_ANALYSIS || supportedRoles !== null) return;
    let active = true;
    setLoading(true);
    setError(null);
    getSupportedRoles()
      .then((roles) => {
        if (active) {
          setSupportedRoles(roles.map((title) => ({ id: title, title, description: null })));
        }
      })
      .catch((err: unknown) => {
        if (active) {
          console.error("Supported role loading failed:", err);
          setError(err instanceof Error ? err.message : "Couldn't load supported roles.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [open, supportedRoles]);

  // Search Supabase roles only in demo mode. Live analysis must use roles exposed by its model.
  useEffect(() => {
    if (!open || !USE_MOCK_ANALYSIS) return;
    const t = setTimeout(() => search(query), 250);
    return () => clearTimeout(t);
  }, [query, open, search]);

  const close = () => {
    setOpen(false);
    setQuery("");
  };

  const handlePick = (role: JobRole) => {
    onSelect(role);
    close();
  };
  const visibleResults = USE_MOCK_ANALYSIS
    ? results
    : (supportedRoles ?? [])
      .filter((role) => role.title.toLowerCase().includes(query.trim().toLowerCase()))
      .sort((a, b) => {
        const lower = query.trim().toLowerCase();
        const aStarts = lower && a.title.toLowerCase().startsWith(lower) ? 0 : 1;
        const bStarts = lower && b.title.toLowerCase().startsWith(lower) ? 0 : 1;
        return aStarts - bStarts || a.title.localeCompare(b.title);
      })
      .slice(0, RESULT_LIMIT);

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel="Choose target role"
        style={({ pressed }) => [styles.trigger, pressed && { opacity: 0.85 }]}
      >
        <Feather name="briefcase" size={16} color={brand.cyan} />
        <Text
          style={[styles.triggerText, !value && styles.triggerPlaceholder]}
          numberOfLines={1}
        >
          {value ? formatRole(value) : "Search and select a role"}
        </Text>
        <Feather name="chevron-down" size={18} color={brand.muted} />
      </Pressable>

      <Modal
        visible={open}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={close}
      >
        <SafeAreaView style={styles.modalRoot} edges={["top", "bottom"]}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Target role</Text>
            <Pressable onPress={close} hitSlop={10} accessibilityRole="button">
              <Text style={styles.cancel}>Cancel</Text>
            </Pressable>
          </View>

          <View style={styles.searchBox}>
            <Feather name="search" size={16} color={brand.muted} />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Search roles, e.g. data analyst"
              placeholderTextColor={brand.muted}
              style={styles.searchInput}
              autoFocus
              autoCorrect={false}
              autoCapitalize="none"
              returnKeyType="search"
              clearButtonMode="while-editing"
            />
            {loading && <ActivityIndicator size="small" color={brand.cyan} />}
          </View>

          <FlatList
            data={visibleResults}
            keyExtractor={(r) => r.id}
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={styles.list}
            ListHeaderComponent={
              !query.trim() && !error ? (
                <Text style={styles.hint}>
                  {USE_MOCK_ANALYSIS
                    ? "Type to search over 3,000 roles, or scroll the list below."
                    : "Choose from roles supported by the live analysis model."}
                </Text>
              ) : undefined
            }
            ListEmptyComponent={
              !loading ? (
                <Text style={styles.empty}>
                  {error ?? `No roles match "${query.trim()}". Try a different word.`}
                </Text>
              ) : undefined
            }
            renderItem={({ item }) => {
              const selected = value?.toLowerCase() === item.title.toLowerCase();
              return (
                <Pressable
                  onPress={() => handlePick(item)}
                  accessibilityRole="button"
                  style={({ pressed }) => [
                    styles.row,
                    selected && styles.rowSelected,
                    pressed && { opacity: 0.8 },
                  ]}
                >
                  <View style={styles.rowText}>
                    <Text style={styles.rowTitle}>{formatRole(item.title)}</Text>
                    {!!item.description && (
                      <Text style={styles.rowDesc} numberOfLines={2}>
                        {item.description}
                      </Text>
                    )}
                  </View>
                  {selected && <Feather name="check" size={18} color={brand.mint} />}
                </Pressable>
              );
            }}
          />
        </SafeAreaView>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  trigger: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 14,
    paddingHorizontal: 14,
    height: 50,
  },
  triggerText: { flex: 1, fontSize: 15, fontWeight: "600", color: brand.text },
  triggerPlaceholder: { color: brand.muted, fontWeight: "500" },

  modalRoot: { flex: 1, backgroundColor: brand.bg },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  modalTitle: { fontSize: 20, fontWeight: "700", color: brand.text },
  cancel: { fontSize: 15, fontWeight: "600", color: brand.cyan },

  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
    paddingHorizontal: 14,
    height: 46,
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 14,
  },
  searchInput: { flex: 1, fontSize: 15, color: brand.text, paddingVertical: 0 },

  list: { paddingHorizontal: spacing.md, paddingBottom: 40 },
  hint: { fontSize: 13, color: brand.muted, marginBottom: spacing.sm },
  empty: { fontSize: 14, color: brand.muted, textAlign: "center", marginTop: spacing.lg },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 12,
    marginBottom: 6,
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
  },
  rowSelected: { borderColor: brand.mint, backgroundColor: brand.tint },
  rowText: { flex: 1 },
  rowTitle: { fontSize: 15, fontWeight: "600", color: brand.text },
  rowDesc: { fontSize: 12, lineHeight: 17, color: brand.muted, marginTop: 2 },
});