import { useEffect, useRef, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Linking,
  Platform,
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

export default function ResetPasswordScreen() {
  const router = useRouter();
  const { mode } = useLocalSearchParams<{ mode?: string }>();
  const isSettingsFlow = mode === "settings";
  const handledUrl = useRef<string | null>(null);
  const [checkingLink, setCheckingLink] = useState(true);
  const [recoveryReady, setRecoveryReady] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    if (isSettingsFlow) {
      void supabase.auth.getSession()
        .then(({ data, error }) => {
          if (error) throw error;
          if (!data.session) throw new Error("No signed-in session is available.");
          if (active) setRecoveryReady(true);
        })
        .catch((error: unknown) => {
          console.error("Could not verify session for password reset:", error);
          if (active) setLinkError("Please sign in again before changing your password.");
        })
        .finally(() => {
          if (active) setCheckingLink(false);
        });
      return () => {
        active = false;
      };
    }

    const handleRecoveryUrl = async (url: string) => {
      if (!active || handledUrl.current === url) return;
      handledUrl.current = url;
      setCheckingLink(true);
      setLinkError(null);

      try {
        const params = getUrlParams(url);
        if (params.has("error") || params.has("error_description")) {
          throw new Error("This password reset link is invalid or has expired.");
        }

        const code = params.get("code");
        const tokenHash = params.get("token_hash");
        const accessToken = params.get("access_token");
        const refreshToken = params.get("refresh_token");
        let session = null;

        if (code) {
          const { data, error } = await supabase.auth.exchangeCodeForSession(code);
          if (error) throw error;
          session = data.session;
        } else if (tokenHash && params.get("type") === "recovery") {
          const { data, error } = await supabase.auth.verifyOtp({
            type: "recovery",
            token_hash: tokenHash,
          });
          if (error) throw error;
          session = data.session;
        } else if (accessToken && refreshToken && params.get("type") === "recovery") {
          const { data, error } = await supabase.auth.setSession({
            access_token: accessToken,
            refresh_token: refreshToken,
          });
          if (error) throw error;
          session = data.session;
        } else {
          throw new Error("The link did not contain a password recovery token.");
        }

        if (!session) throw new Error("The recovery link did not create a session.");
        if (active) setRecoveryReady(true);
      } catch (error) {
        console.error("Could not validate password recovery link:", error);
        if (active) setLinkError("This password reset link is invalid or has expired. Request a new one.");
      } finally {
        if (active) setCheckingLink(false);
      }
    };

    const subscription = Linking.addEventListener("url", ({ url }) => {
      void handleRecoveryUrl(url);
    });

    void Linking.getInitialURL()
      .then((url) => {
        if (url) return handleRecoveryUrl(url);
        if (active) {
          setLinkError("Open the password reset link from your email, or request a new one.");
          setCheckingLink(false);
        }
        return undefined;
      })
      .catch((error: unknown) => {
        console.error("Could not read password recovery link:", error);
        if (active) {
          setLinkError("We couldn't read the reset link. Open it again or request a new one.");
          setCheckingLink(false);
        }
      });

    return () => {
      active = false;
      subscription.remove();
    };
  }, [isSettingsFlow]);

  const savePassword = async () => {
    if (password.length < 8) {
      setFormError("Choose a password with at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setFormError("The passwords don't match.");
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      router.replace(isSettingsFlow ? "/(tabs)/settings" : "/(tabs)");
    } catch (error) {
      console.error("Could not update password from recovery flow:", error);
      setFormError("We couldn't update your password. Request a new reset link and try again.");
    } finally {
      setSaving(false);
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
        <KeyboardAvoidingView
          style={styles.fill}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <ScrollView
            contentContainerStyle={styles.content}
            keyboardShouldPersistTaps="handled"
          >
            <Pressable
              onPress={() => router.replace(isSettingsFlow ? "/(tabs)/settings" : "/login")}
              accessibilityRole="button"
              style={styles.backButton}
            >
              <Feather name="arrow-left" size={18} color={brand.cyan} />
              <Text style={styles.backText}>Back to sign in</Text>
            </Pressable>

            <View style={styles.card}>
              <View style={styles.iconCircle}>
                <Feather name="key" size={22} color={brand.cyan} />
              </View>
              <Text style={styles.title}>
                {isSettingsFlow ? "Reset password" : "Create a new password"}
              </Text>

              {checkingLink ? (
                <View style={styles.statusRow}>
                  <ActivityIndicator color={brand.cyan} />
                  <Text style={styles.subtitle}>
                    {isSettingsFlow ? "Checking your account…" : "Checking your reset link…"}
                  </Text>
                </View>
              ) : linkError ? (
                <>
                  <Text accessibilityRole="alert" style={styles.error}>{linkError}</Text>
                  <Pressable
                    onPress={() => router.replace("/forgot-password")}
                    accessibilityRole="button"
                    style={({ pressed }) => [
                      styles.primaryButton,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.primaryButtonText}>Request a new link</Text>
                  </Pressable>
                </>
              ) : recoveryReady ? (
                <>
                  <Text style={styles.subtitle}>
                    {isSettingsFlow
                      ? "Choose a new password for your signed-in account."
                      : "Choose a new password for your account."}
                  </Text>
                  <TextInput
                    value={password}
                    onChangeText={setPassword}
                    placeholder="New password"
                    placeholderTextColor={brand.muted}
                    secureTextEntry
                    textContentType="newPassword"
                    autoComplete="new-password"
                    autoCapitalize="none"
                    editable={!saving}
                    accessibilityLabel="New password"
                    style={styles.input}
                  />
                  <TextInput
                    value={confirmPassword}
                    onChangeText={setConfirmPassword}
                    placeholder="Confirm new password"
                    placeholderTextColor={brand.muted}
                    secureTextEntry
                    textContentType="newPassword"
                    autoComplete="new-password"
                    autoCapitalize="none"
                    editable={!saving}
                    accessibilityLabel="Confirm new password"
                    style={styles.input}
                  />
                  <Text style={styles.helper}>Use at least 8 characters.</Text>
                  {formError && (
                    <Text accessibilityRole="alert" style={styles.error}>{formError}</Text>
                  )}
                  <Pressable
                    onPress={() => void savePassword()}
                    disabled={saving}
                    accessibilityRole="button"
                    style={({ pressed }) => [
                      styles.primaryButton,
                      (pressed || saving) && styles.pressed,
                    ]}
                  >
                    {saving ? <ActivityIndicator color={brand.onGradient} /> : (
                      <Text style={styles.primaryButtonText}>Update password</Text>
                    )}
                  </Pressable>
                </>
              ) : null}
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

function getUrlParams(url: string): URLSearchParams {
  const query = url.split("?")[1]?.split("#")[0] ?? "";
  const fragment = url.split("#")[1] ?? "";
  return new URLSearchParams([query, fragment].filter(Boolean).join("&"));
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: brand.bg },
  safeArea: { flex: 1 },
  fill: { flex: 1 },
  glow: { position: "absolute", top: 0, left: 0, right: 0, height: 280 },
  content: { flexGrow: 1, justifyContent: "center", padding: 20 },
  backButton: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 12 },
  backText: { color: brand.cyan, fontSize: 14, fontWeight: "600" },
  card: {
    width: "100%",
    maxWidth: 420,
    alignSelf: "center",
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 20,
    padding: 24,
  },
  iconCircle: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: brand.tint,
    marginBottom: 20,
  },
  title: { fontFamily: SERIF, fontSize: 28, color: brand.text, marginBottom: 8 },
  subtitle: { color: brand.muted, fontSize: 15, lineHeight: 22, marginBottom: 20 },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 12, marginTop: 12 },
  input: {
    backgroundColor: brand.surface,
    borderWidth: 1,
    borderColor: brand.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: brand.text,
    fontSize: 15,
    marginBottom: 12,
  },
  helper: { color: brand.muted, fontSize: 13, marginBottom: 12 },
  error: { color: "#B42318", fontSize: 13, lineHeight: 19, marginVertical: 8 },
  primaryButton: {
    minHeight: 50,
    borderRadius: 12,
    backgroundColor: brand.cyan,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20,
    paddingVertical: 14,
    marginTop: 4,
  },
  primaryButtonText: { color: brand.onGradient, fontSize: 15, fontWeight: "700" },
  pressed: { opacity: 0.8 },
});
