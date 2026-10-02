import { ActivityIndicator, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";
import { Feather } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";
import { radius, spacing } from "@/components/ui/theme";
import { useEffect, useState } from "react";

// Muted dark-green palette
const brand = {
  bg: "#081412",
  surface: "#101D1A",
  surfaceLight: "#14231F",
  border: "rgba(255,255,255,0.08)",
  text: "#E8F0ED",
  muted: "#91A29D",
  green: "#7CC9A5",
  greenSoft: "#A8D8B9",
  onGradient: "#092019",
};

const SERIF = Platform.select({
  ios: "Georgia",
  android: "serif",
  default: "serif",
});

const QUICK_ACTIONS = [
  { icon: "search", label: "View my results", route: "/analysis" },
  { icon: "book-open", label: "Browse resources", route: "/courses" },
] as const;

export default function HomeScreen() {
  const router = useRouter();
  const [userName, setUserName] = useState<string | null>(null);

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
            return;
          }

          const { data } = await supabase
            .from("profiles")
            .select("full_name")
            .eq("id", user.id)
            .single();

          if (data && data.full_name) {
            setUserName(data.full_name.trim().split(/\s+/)[0]);
            return;
          }
        }

        setUserName("there");
      } catch (err) {
        console.error("Error fetching profile name:", err);
        if (isMounted) setUserName("there");
      }
    }

    fetchUserProfile();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <View style={styles.root}>
      {/* Very subtle background glow */}
      <LinearGradient
        colors={[
          "rgba(124,201,165,0.07)",
          "rgba(124,201,165,0.02)",
          "rgba(124,201,165,0)",
        ]}
        style={styles.glow}
        pointerEvents="none"
      />

      <SafeAreaView style={styles.safeArea} edges={["top"]}>
        <ScrollView
          contentContainerStyle={styles.container}
          showsVerticalScrollIndicator={false}
        >
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.greeting}>Hello, {userName ?? "there"}</Text>
            <Text style={styles.title}>
              Let's build your career together.
            </Text>
          </View>

          {/* Main card */}
          <View style={styles.heroBorder}>
            <View style={styles.heroInner}>
              <View style={styles.heroRow}>
                <View style={styles.iconCircle}>
                  <Feather
                    name="file-text"
                    size={21}
                    color={brand.green}
                  />
                </View>

                <View style={styles.heroText}>
                  <Text style={styles.heroTitle}>
                    Analyze your skills
                  </Text>

                  <Text style={styles.heroSubtitle}>
                    Upload your resume and see how ready you are for your
                    target roles.
                  </Text>
                </View>
              </View>

              <Pressable
                onPress={() => router.push("/resume-upload")}
                accessibilityRole="button"
                style={({ pressed }) => [
                  styles.buttonWrap,
                  pressed && { opacity: 0.85 },
                ]}
              >
                <LinearGradient
                  colors={[brand.green, brand.greenSoft]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.button}
                >
                  <Text style={styles.buttonText}>
                    Start analysis
                  </Text>
                </LinearGradient>
              </Pressable>
            </View>
          </View>

          {/* Quick actions */}
          <Text style={styles.sectionTitle}>
            Quick actions
          </Text>

          <View style={styles.quickRow}>
            {QUICK_ACTIONS.map((a) => (
              <Pressable
                key={a.route}
                onPress={() => router.push(a.route)}
                accessibilityRole="button"
                style={({ pressed }) => [
                  styles.actionBox,
                  pressed && { opacity: 0.8 },
                ]}
              >
                <View style={styles.actionIconCircle}>
                  <Feather
                    name={a.icon}
                    size={19}
                    color={brand.green}
                  />
                </View>

                <Text style={styles.actionText}>
                  {a.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: brand.bg,
  },

  safeArea: {
    flex: 1,
  },

  glow: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 280,
  },

  container: {
    padding: spacing.md,
    paddingBottom: 40,
  },

  header: {
    marginTop: spacing.md,
    marginBottom: spacing.lg,
  },

  greeting: {
    fontSize: 15,
    color: brand.muted,
    marginBottom: 6,
  },

  title: {
    fontFamily: SERIF,
    fontSize: 32,
    lineHeight: 37,
    fontWeight: "400",
    letterSpacing: -0.5,
    color: brand.text,
  },

  heroBorder: {
    borderRadius: radius.lg ?? 20,
    borderWidth: 1,
    borderColor: "rgba(124,201,165,0.18)",
    marginBottom: spacing.lg,
    backgroundColor: brand.surface,
  },

  heroInner: {
    backgroundColor: brand.surface,
    borderRadius: radius.lg ?? 20,
    padding: spacing.lg,
  },

  heroRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },

  heroText: {
    flex: 1,
  },

  heroTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: brand.text,
    marginBottom: 4,
  },

  heroSubtitle: {
    fontSize: 14,
    lineHeight: 20,
    color: brand.muted,
  },

  iconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(124,201,165,0.08)",
    borderWidth: 1,
    borderColor: "rgba(124,201,165,0.10)",
  },

  buttonWrap: {
    borderRadius: 999,
    overflow: "hidden",
  },

  button: {
    height: 48,
    alignItems: "center",
    justifyContent: "center",
  },

  buttonText: {
    color: brand.onGradient,
    fontSize: 15,
    fontWeight: "700",
  },

  sectionTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: brand.text,
    marginBottom: spacing.md,
  },

  quickRow: {
    flexDirection: "row",
    gap: spacing.md,
  },

  actionBox: {
    flex: 1,
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 16,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    gap: spacing.sm,
  },

  actionIconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(124,201,165,0.07)",
  },

  actionText: {
    fontSize: 13,
    fontWeight: "600",
    color: brand.text,
    textAlign: "center",
  },
});