import { useCallback, useEffect, useState } from "react";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { brand, SERIF } from "@/components/ui/theme";
import { supabase } from "@/lib/supabase";
import { useAppData } from "@/state/appdatacontext";

export default function SettingsScreen() {
  const router = useRouter();
  const {
    analysisHistory,
    historyLoading,
    historyError,
    showHistoricalAnalysis,
  } = useAppData();
  const [userId, setUserId] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [savingUsername, setSavingUsername] = useState(false);

  const loadProfile = useCallback(async () => {
    setLoadingProfile(true);
    try {
      const { data: { user }, error: userError } = await supabase.auth.getUser();
      if (userError) throw userError;
      if (!user) {
        setUserId(null);
        setEmail("");
        setUsername("");
        return;
      }

      setUserId(user.id);
      setEmail(user.email ?? "");
      const metadataName = user.user_metadata?.full_name;
      const { data, error } = await supabase
        .from("profiles")
        .select("full_name")
        .eq("id", user.id)
        .maybeSingle();
      if (error) throw error;

      const profileName = data?.full_name;
      setUsername(
        typeof profileName === "string" && profileName.trim()
          ? profileName
          : typeof metadataName === "string" ? metadataName : "",
      );
    } catch (error) {
      console.error("Could not load account settings:", error);
      Alert.alert("Settings unavailable", "We couldn't load your account details. Please try again.");
    } finally {
      setLoadingProfile(false);
    }
  }, []);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  const handleSaveUsername = async () => {
    const nextUsername = username.trim();
    if (!userId) {
      Alert.alert("Sign in required", "Please sign in again to update your username.");
      return;
    }
    if (!nextUsername) {
      Alert.alert("Username required", "Enter a name to show on your account.");
      return;
    }
    if (nextUsername.length > 80) {
      Alert.alert("Username too long", "Use 80 characters or fewer.");
      return;
    }

    setSavingUsername(true);
    try {
      const { error: profileError } = await supabase
        .from("profiles")
        .upsert({ id: userId, full_name: nextUsername, updated_at: new Date().toISOString() });
      if (profileError) throw profileError;
      setUsername(nextUsername);

      const { error: authError } = await supabase.auth.updateUser({
        data: { full_name: nextUsername },
      });
      if (authError) {
        console.error("Profile display name saved, but auth metadata update failed:", authError);
        Alert.alert(
          "Name saved",
          "Your profile name was saved, but the account greeting may take a moment to update. Please reopen Settings if it remains out of date.",
        );
        return;
      }
      Alert.alert("Username updated", "Your account name has been saved.");
    } catch (error) {
      console.error("Could not update username:", error);
      Alert.alert("Update failed", "We couldn't save your username. Please try again.");
    } finally {
      setSavingUsername(false);
    }
  };

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={[brand.tint, "transparent"]}
        style={styles.glow}
        pointerEvents="none"
      />
      <SafeAreaView style={styles.safeArea} edges={["top"]}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <Text style={styles.title}>Settings</Text>
            <Text style={styles.subtitle}>Manage your account and revisit previous resume analyses.</Text>
          </View>

          <View style={styles.section}>
          <View style={styles.sectionHeading}>
            <Feather name="user" size={18} color={brand.cyan} />
            <Text style={styles.sectionTitle}>Account</Text>
          </View>
          {loadingProfile ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color={brand.cyan} />
              <Text style={styles.helper}>Loading account details…</Text>
            </View>
          ) : (
            <>
              <Text style={styles.label}>Email</Text>
              <TextInput
                value={email}
                editable={false}
                style={[styles.input, styles.readOnlyInput]}
                accessibilityLabel="Account email"
              />
              <Text style={styles.label}>Username / display name</Text>
              <TextInput
                value={username}
                onChangeText={setUsername}
                placeholder="Your name"
                placeholderTextColor={brand.muted}
                autoCapitalize="words"
                maxLength={80}
                style={styles.input}
                accessibilityLabel="Username or display name"
              />
              <Pressable
                onPress={() => void handleSaveUsername()}
                disabled={savingUsername || !userId}
                style={({ pressed }) => [
                  styles.primaryButton,
                  (pressed || savingUsername) && styles.pressed,
                  (!userId || savingUsername) && styles.disabled,
                ]}
              >
                {savingUsername ? <ActivityIndicator color={brand.onGradient} /> : (
                  <Text style={styles.primaryButtonText}>Save username</Text>
                )}
              </Pressable>
            </>
          )}
          </View>

          <View style={styles.section}>
          <View style={styles.sectionHeading}>
            <Feather name="lock" size={18} color={brand.cyan} />
            <Text style={styles.sectionTitle}>Password</Text>
          </View>
          <Pressable
            onPress={() => router.push({ pathname: "/reset-password", params: { mode: "settings" } })}
            accessibilityRole="button"
            accessibilityLabel="Open password reset screen"
            style={({ pressed }) => [
              styles.secondaryButton,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.secondaryButtonText}>Reset password</Text>
          </Pressable>
          </View>

          <View style={styles.historySection}>
          <View style={styles.sectionHeading}>
            <Feather name="clock" size={18} color={brand.cyan} />
            <Text style={styles.sectionTitle}>Analysis history</Text>
          </View>
          <Text style={styles.helper}>
            Your 50 most recent saved resume analyses.
          </Text>

          {historyLoading ? (
            <View style={styles.emptyState}>
              <ActivityIndicator size="large" color={brand.cyan} />
              <Text style={styles.helper}>Loading saved analyses…</Text>
            </View>
          ) : historyError ? (
            <View style={styles.emptyState}>
              <Feather name="alert-circle" size={24} color={brand.cyan} />
              <Text style={styles.stateText}>{historyError}</Text>
            </View>
          ) : analysisHistory.length === 0 ? (
            <View style={styles.emptyState}>
              <Feather name="file-text" size={24} color={brand.cyan} />
              <Text style={styles.stateTitle}>No past analyses yet</Text>
              <Text style={styles.stateText}>
                Saved results will appear here after you analyze a resume.
              </Text>
              <Pressable
                onPress={() => router.push("/resume-upload")}
                style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
              >
                <Text style={styles.primaryButtonText}>Analyze a resume</Text>
              </Pressable>
            </View>
          ) : (
            analysisHistory.map((entry) => {
              const date = new Date(entry.createdAt);
              const dateLabel = Number.isNaN(date.getTime())
                ? "Date unavailable"
                : date.toLocaleString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                });

              return (
                <Pressable
                  key={entry.id}
                  onPress={() => {
                    showHistoricalAnalysis(entry);
                    router.replace("/(tabs)/analysis");
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`View ${entry.analysis.targetRole} analysis from ${dateLabel}`}
                  style={({ pressed }) => [styles.historyCard, pressed && styles.pressed]}
                >
                  <View style={styles.cardTop}>
                    <View style={styles.roleWrap}>
                      <Text style={styles.role} numberOfLines={1}>{entry.analysis.targetRole}</Text>
                      <Text style={styles.date}>{dateLabel}</Text>
                    </View>
                    <View style={styles.scoreBadge}>
                      <Text style={styles.score}>{Math.round(entry.analysis.readiness)}%</Text>
                    </View>
                  </View>
                  <Text style={styles.fileName} numberOfLines={1}>
                    {entry.analysis.resumeFileName}
                  </Text>
                  <View style={styles.cardBottom}>
                    <Text style={styles.summary}>
                      {entry.analysis.covered.length} skills matched
                      <Text style={styles.dot}> · </Text>
                      {entry.analysis.gaps.length} gaps
                    </Text>
                    <Feather name="chevron-right" size={18} color={brand.muted} />
                  </View>
                </Pressable>
              );
            })
          )}
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: brand.bg },
  safeArea: { flex: 1 },
  glow: { position: "absolute", top: 0, left: 0, right: 0, height: 280 },
  content: { padding: 16, paddingBottom: 36 },
  header: { marginTop: 16, marginBottom: 20 },
  title: { fontFamily: SERIF, color: brand.text, fontSize: 28, textAlign: "center" },
  subtitle: { color: brand.muted, fontSize: 14, lineHeight: 20, textAlign: "center", marginTop: 8 },
  section: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  historySection: { marginTop: 4 },
  sectionHeading: { flexDirection: "row", alignItems: "center", gap: 9, marginBottom: 14 },
  sectionTitle: { color: brand.text, fontSize: 18, fontWeight: "700" },
  label: { color: brand.text, fontSize: 13, fontWeight: "600", marginBottom: 7, marginTop: 12 },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 12,
    paddingHorizontal: 13,
    color: brand.text,
    backgroundColor: brand.surface,
    fontSize: 15,
    marginBottom: 10,
  },
  readOnlyInput: { backgroundColor: "#F4F7FA", color: brand.muted },
  helper: { color: brand.muted, fontSize: 13, lineHeight: 19, marginBottom: 12 },
  loadingRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 8 },
  primaryButton: {
    minHeight: 46,
    backgroundColor: brand.cyan,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20,
    marginTop: 6,
  },
  primaryButtonText: { color: brand.onGradient, fontSize: 14, fontWeight: "700" },
  secondaryButton: {
    minHeight: 46,
    borderWidth: 1,
    borderColor: brand.cyan,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20,
    marginTop: 6,
  },
  secondaryButtonText: { color: brand.cyan, fontSize: 14, fontWeight: "700" },
  disabled: { opacity: 0.6 },
  pressed: { opacity: 0.78 },
  emptyState: { alignItems: "center", paddingHorizontal: 18, paddingVertical: 28 },
  stateTitle: { color: brand.text, fontSize: 17, fontWeight: "700", marginTop: 12 },
  stateText: { color: brand.muted, fontSize: 13, lineHeight: 19, textAlign: "center", marginTop: 10 },
  historyCard: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    padding: 16,
    marginTop: 10,
  },
  cardTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  roleWrap: { flex: 1 },
  role: { color: brand.text, fontSize: 17, fontWeight: "700", textTransform: "capitalize" },
  date: { color: brand.muted, fontSize: 12, marginTop: 4 },
  scoreBadge: { backgroundColor: "rgba(0,122,135,0.12)", borderRadius: 999, paddingVertical: 7, paddingHorizontal: 11 },
  score: { color: brand.cyan, fontWeight: "800", fontSize: 15 },
  fileName: { color: brand.muted, fontSize: 13, marginTop: 14 },
  cardBottom: {
    borderTopWidth: 1,
    borderTopColor: brand.border,
    marginTop: 14,
    paddingTop: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  summary: { color: brand.text, fontSize: 13, fontWeight: "600" },
  dot: { color: brand.muted },
});
