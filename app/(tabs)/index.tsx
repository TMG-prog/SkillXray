import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { brand, radius, spacing, SERIF } from "@/components/ui/theme";
import { useEffect, useState } from "react";
import { useAppData } from "@/state/appdatacontext";
import RolePicker, { formatRole, type JobRole } from "@/components/RolePicker";

const QUICK_ACTIONS = [
  { icon: "search", label: "View my results", route: "/analysis" },
  { icon: "book-open", label: "Browse resources", route: "/courses" },
] as const;

export default function HomeScreen() {
  const router = useRouter();
  const { analysis } = useAppData();
  const [userName, setUserName] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [isUpdatingRole, setIsUpdatingRole] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function fetchUserProfile() {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!isMounted) return;

        if (user) {
          const authName = user.user_metadata?.full_name;
          if (typeof authName === "string" && authName.trim()) {
            setUserName(authName.trim().split(/\s+/)[0]);
          }

          const { data } = await supabase
            .from("profiles")
            .select("full_name, target_role")
            .eq("id", user.id)
            .single();

          if (data) {
            if (data.full_name && !userName) {
              setUserName(data.full_name.trim().split(/\s+/)[0]);
            }
            if (data.target_role) {
              setSelectedRole(data.target_role);
            }
          }
          return;
        }

        setUserName("there");
      } catch (err) {
        console.error("Error fetching profile name:", err);
        if (isMounted) setUserName("there");
      }
    }

    fetchUserProfile();
    return () => { isMounted = false; };
  }, []);

  const handleSelectRole = async (role: JobRole) => {
    const previous = selectedRole;
    setSelectedRole(role.title);
    setIsUpdatingRole(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (user) {
        const { error } = await supabase
          .from("profiles")
          .upsert({ id: user.id, target_role: role.title, updated_at: new Date().toISOString() });
        if (error) throw error;
      }
    } catch (err) {
      console.error("Error updating target role:", err);
      setSelectedRole(previous); // roll back if saving failed
    } finally {
      setIsUpdatingRole(false);
    }
  };

  const hasAnalysis = !!analysis;
  const roleLabel = selectedRole ? formatRole(selectedRole) : null;

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={[brand.tint, "transparent"]}
        style={styles.glow}
        pointerEvents="none"
      />

      <SafeAreaView style={styles.safeArea} edges={["top"]}>
        <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerTop}>
              <Text style={styles.greeting}>Hello, {userName ?? "there"}</Text>
              <Pressable onPress={() => supabase.auth.signOut()} hitSlop={8} accessibilityRole="button">
                <Text style={styles.signOut}>Sign out</Text>
              </Pressable>
            </View>
            <Text style={styles.title}>See how your skills compare to the current job market.</Text>
          </View>

          {/* Target Role Selection Section */}
          <View style={styles.roleContainer}>
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionTitle}>Target Role</Text>
              {isUpdatingRole && <Text style={styles.savingText}>Saving...</Text>}
            </View>
            <Text style={styles.sectionSubtitle}>
              Select your target role to tailor resume analysis and skill recommendations.
            </Text>

            <RolePicker
              value={selectedRole}
              onSelect={handleSelectRole}
              disabled={isUpdatingRole}
            />
          </View>

          {/* Hero / Readiness Score Card */}
          <View style={styles.heroBorder}>
            <View style={styles.heroInner}>
              <View style={styles.heroRow}>
                <View style={styles.iconCircle}>
                  <Feather name="file-text" size={21} color={brand.cyan} />
                </View>

                <View style={styles.heroText}>
                  <Text style={styles.heroTitle}>
                    {hasAnalysis ? "Your readiness score" : "Analyze your skills"}
                  </Text>
                  <Text style={styles.heroSubtitle}>
                    {!roleLabel
                      ? "Choose a target role above, then upload your resume to see how ready you are."
                      : hasAnalysis
                        ? `You're at ${Math.round(analysis!.readiness)}% readiness for target role "${roleLabel}". Re-run the analysis any time you update your resume.`
                        : `Upload your resume to see how ready you are for the ${roleLabel} role.`}
                  </Text>
                </View>

                {hasAnalysis && (
                  <View style={styles.readinessChip}>
                    <Text style={styles.readinessChipText}>{Math.round(analysis!.readiness)}%</Text>
                  </View>
                )}
              </View>

              <Pressable
                onPress={() => router.push("/resume-upload")}
                disabled={!selectedRole}
                accessibilityRole="button"
                style={({ pressed }) => [
                  styles.buttonWrap,
                  !selectedRole && { opacity: 0.4 },
                  pressed && { opacity: 0.85 },
                ]}
              >
                <LinearGradient
                  colors={[brand.cyan, brand.mint]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.button}
                >
                  <Text style={styles.buttonText}>
                    {hasAnalysis ? "Re-analyze your resume" : "Start analysis"}
                  </Text>
                </LinearGradient>
              </Pressable>
            </View>
          </View>

          {/* Quick Actions Section */}
          <Text style={styles.sectionTitle}>Quick actions</Text>

          <View style={styles.quickRow}>
            {QUICK_ACTIONS.map((a) => (
              <Pressable
                key={a.route}
                onPress={() => router.push(a.route)}
                accessibilityRole="button"
                style={({ pressed }) => [styles.actionBox, pressed && { opacity: 0.8 }]}
              >
                <View style={styles.actionIconCircle}>
                  <Feather name={a.icon} size={19} color={brand.cyan} />
                </View>
                <Text style={styles.actionText}>{a.label}</Text>
              </Pressable>
            ))}
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
  container: { padding: spacing.md, paddingBottom: 40 },
  header: { marginTop: spacing.md, marginBottom: spacing.lg },
  headerTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  signOut: { fontSize: 14, fontWeight: "600", color: brand.cyan },
  greeting: { fontSize: 15, color: brand.muted, marginBottom: 6 },
  title: { fontFamily: SERIF, fontSize: 32, lineHeight: 37, fontWeight: "400", letterSpacing: -0.5, color: brand.text },

  // Target Role Section
  roleContainer: { marginBottom: spacing.lg },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  sectionSubtitle: { fontSize: 13, color: brand.muted, marginBottom: spacing.sm },
  savingText: { fontSize: 12, color: brand.cyan, fontWeight: "600" },

  // Hero Card
  heroBorder: {
    borderRadius: radius.lg ?? 20,
    borderWidth: 1,
    borderColor: brand.border,
    marginBottom: spacing.lg,
    backgroundColor: brand.surface,
  },
  heroInner: { backgroundColor: brand.surface, borderRadius: radius.lg ?? 20, padding: spacing.lg },
  heroRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md, marginBottom: spacing.lg },
  heroText: { flex: 1 },
  heroTitle: { fontSize: 18, fontWeight: "700", color: brand.text, marginBottom: 4 },
  heroSubtitle: { fontSize: 14, lineHeight: 20, color: brand.muted },
  iconCircle: {
    width: 44, height: 44, borderRadius: 22,
    alignItems: "center", justifyContent: "center",
    backgroundColor: brand.tint,
    borderWidth: 1, borderColor: brand.border,
  },
  readinessChip: {
    backgroundColor: brand.tint,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
    alignSelf: "flex-start",
  },
  readinessChipText: { color: brand.mint, fontWeight: "700", fontSize: 13 },
  buttonWrap: { borderRadius: 999, overflow: "hidden" },
  button: { height: 48, alignItems: "center", justifyContent: "center" },
  buttonText: { color: brand.onGradient, fontSize: 15, fontWeight: "700" },

  // Section & Quick Actions
  sectionTitle: { fontSize: 18, fontWeight: "700", color: brand.text, marginBottom: spacing.xs ?? 8 },
  quickRow: { flexDirection: "row", gap: spacing.md, marginTop: spacing.xs },
  actionBox: {
    flex: 1, backgroundColor: brand.surface, borderWidth: 1, borderColor: brand.border,
    borderRadius: 16, paddingVertical: spacing.lg, paddingHorizontal: spacing.md,
    alignItems: "center", gap: spacing.sm,
  },
  actionIconCircle: {
    width: 40, height: 40, borderRadius: 20,
    alignItems: "center", justifyContent: "center",
    backgroundColor: brand.tint,
  },
  actionText: { fontSize: 13, fontWeight: "600", color: brand.text, textAlign: "center" },
});