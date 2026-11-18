import { useState } from "react";
import { useRouter } from "expo-router";
import { makeRedirectUri } from "expo-auth-session";
import { Feather } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
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

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const sendResetEmail = async () => {
    const normalizedEmail = email.trim();
    if (!normalizedEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      setErrorMessage("Enter a valid email address.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const redirectTo = makeRedirectUri({
        scheme: "skillxray",
        path: "reset-password",
      });
      const { error } = await supabase.auth.resetPasswordForEmail(normalizedEmail, { redirectTo });
      if (error) throw error;
      setSent(true);
    } catch (error) {
      console.error("Could not send password recovery email:", error);
      setErrorMessage("We couldn't send a reset email. Check your connection and try again.");
    } finally {
      setLoading(false);
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
              onPress={() => router.replace("/login")}
              accessibilityRole="button"
              style={styles.backButton}
            >
              <Feather name="arrow-left" size={18} color={brand.cyan} />
              <Text style={styles.backText}>Back to sign in</Text>
            </Pressable>

            <View style={styles.card}>
              <View style={styles.iconCircle}>
                <Feather name="lock" size={22} color={brand.cyan} />
              </View>
              <Text style={styles.title}>{sent ? "Check your email" : "Forgot password?"}</Text>
              <Text style={styles.subtitle}>
                {sent
                  ? "If an account exists for that email, we'll send a link to reset its password."
                  : "Enter the email address linked to your account and we'll send you a reset link."}
              </Text>

              {!sent && (
                <>
                  <TextInput
                    value={email}
                    onChangeText={setEmail}
                    placeholder="Email"
                    placeholderTextColor={brand.muted}
                    keyboardType="email-address"
                    textContentType="emailAddress"
                    autoComplete="email"
                    autoCapitalize="none"
                    autoCorrect={false}
                    editable={!loading}
                    accessibilityLabel="Email address"
                    style={styles.input}
                  />
                  {errorMessage && (
                    <Text accessibilityRole="alert" style={styles.error}>
                      {errorMessage}
                    </Text>
                  )}
                  <Pressable
                    onPress={() => void sendResetEmail()}
                    disabled={loading}
                    accessibilityRole="button"
                    style={({ pressed }) => [
                      styles.primaryButton,
                      (pressed || loading) && styles.pressed,
                    ]}
                  >
                    {loading ? <ActivityIndicator color={brand.onGradient} /> : (
                      <Text style={styles.primaryButtonText}>Send reset link</Text>
                    )}
                  </Pressable>
                </>
              )}

              {sent && (
                <Pressable
                  onPress={() => router.replace("/login")}
                  accessibilityRole="button"
                  style={({ pressed }) => [
                    styles.primaryButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.primaryButtonText}>Return to sign in</Text>
                </Pressable>
              )}
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
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
  subtitle: { color: brand.muted, fontSize: 15, lineHeight: 22, marginBottom: 24 },
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
  error: { color: "#B42318", fontSize: 13, lineHeight: 18, marginBottom: 12 },
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
