import { useState } from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { supabase } from "@/lib/supabase";

export const theme = {
  bg: "#03110F",
  card: "rgba(8, 26, 24, 0.88)",
  field: "#071614",
  border: "rgba(255,255,255,0.14)",
  text: "#EEF7F4",
  muted: "#8FA9A4",
  cyan: "#25D9D0",
  mint: "#C6F3A8",
  onGradient: "#04211E",
  error: "#FF8F86",
};
const GRADIENT = [theme.cyan, theme.mint] as const;
const SERIF = Platform.select({ ios: "Georgia", android: "serif", default: "serif" });

const BARS = [10, 22, 15, 30, 19, 26];

type Mode = "signIn" | "signUp";

export default function AuthForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signIn");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [focused, setFocused] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const isSignIn = mode === "signIn";

  async function submit() {
    setError(null);
    setNotice(null);

    if (!email.trim() || !password || (!isSignIn && !fullName.trim())) {
      setError("Please fill in all required fields.");
      return;
    }

    setLoading(true);

    if (isSignIn) {
      const { error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (error) {
        setError("Email or password is incorrect.");
      }
    } else {
      const { data, error: signUpError } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: {
            full_name: fullName.trim(),
          },
        },
      });

      if (signUpError) {
        setError(signUpError.message);
      } else {
        if (data.user) {
          const { error: profileError } = await supabase
            .from("profiles")
            .upsert(
              { id: data.user.id, full_name: fullName.trim() },
              { onConflict: "id" }
            );

          if (profileError) {
            console.warn("Profile sync warning:", profileError.message);
          }
        }

        setNotice("Account created successfully!");
        try {
          await supabase.auth.registerPasskey();
        } catch {
          // Passkey optional fallback
        }
       
      }
    }

    setLoading(false);
  }

  async function handlePasskeySignIn() {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithPasskey();
      if (error) {
        setError("Passkey sign-in failed or was cancelled.");
      }
    } catch {
      setError("Passkeys are not supported on this device.");
    }
    setLoading(false);
  }

  return (
    <View style={styles.card}>
      <View style={styles.mark} accessibilityElementsHidden>
        {BARS.map((h, i) => (
          <LinearGradient
            key={i}
            colors={[theme.mint, theme.cyan]}
            style={[styles.bar, { height: h }]}
          />
        ))}
      </View>

      <Text style={styles.title}>
        {isSignIn ? "Sign in to SkillXray" : "Create your account"}
      </Text>
      <Text style={styles.subtitle}>
        {isSignIn
          ? "See the skills your experience shows."
          : "Set up your profile to get started."}
      </Text>

      {!isSignIn && (
        <>
          <Text style={styles.label}>Full Name</Text>
          <TextInput
            style={[styles.input, focused === "name" && styles.inputFocused]}
            value={fullName}
            onChangeText={setFullName}
            onFocus={() => setFocused("name")}
            onBlur={() => setFocused(null)}
            placeholder="First and last name"
            placeholderTextColor={theme.muted}
          />
        </>
      )}

      <Text style={styles.label}>Email</Text>
      <TextInput
        style={[styles.input, focused === "email" && styles.inputFocused]}
        value={email}
        onChangeText={setEmail}
        onFocus={() => setFocused("email")}
        onBlur={() => setFocused(null)}
        placeholder="you@example.com"
        placeholderTextColor={theme.muted}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
      />

      <Text style={styles.label}>Password</Text>
      <View>
        <TextInput
          style={[
            styles.input,
            styles.passwordInput,
            focused === "password" && styles.inputFocused,
          ]}
          value={password}
          onChangeText={setPassword}
          onFocus={() => setFocused("password")}
          onBlur={() => setFocused(null)}
          placeholder="At least 8 characters"
          placeholderTextColor={theme.muted}
          secureTextEntry={!showPassword}
          autoCapitalize="none"
        />
        <Pressable
          style={styles.toggle}
          onPress={() => setShowPassword((v) => !v)}
          hitSlop={8}
        >
          <Text style={styles.toggleText}>{showPassword ? "Hide" : "Show"}</Text>
        </Pressable>
      </View>

      {error && <Text style={styles.error}>{error}</Text>}
      {notice && <Text style={styles.notice}>{notice}</Text>}

      <Pressable
        onPress={submit}
        disabled={loading}
        style={({ pressed }) => [
          styles.buttonWrap,
          pressed && { opacity: 0.85 },
          loading && { opacity: 0.7 },
        ]}
      >
        <LinearGradient
          colors={GRADIENT}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.button}
        >
          {loading ? (
            <ActivityIndicator color={theme.onGradient} />
          ) : (
            <Text style={styles.buttonText}>
              {isSignIn ? "Sign in" : "Complete Sign Up"}
            </Text>
          )}
        </LinearGradient>
      </Pressable>

      {isSignIn && (
        <Pressable style={styles.passkeyButton} onPress={handlePasskeySignIn} disabled={loading}>
          <Text style={styles.passkeyButtonText}>Sign in with  Passkey</Text>
        </Pressable>
      )}

      <Pressable
        style={styles.switch}
        onPress={() => {
          setMode(isSignIn ? "signUp" : "signIn");
          setError(null);
          setNotice(null);
        }}
      >
        <Text style={styles.switchText}>
          {isSignIn ? "New here? Create an account" : "Have an account? Sign in"}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: "100%",
    maxWidth: 360,
    backgroundColor: theme.card,
    padding: 24,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.border,
  },
  mark: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "center",
    gap: 4,
    height: 30,
    marginBottom: 20,
  },
  bar: { width: 5, borderRadius: 3 },
  title: {
    fontFamily: SERIF,
    fontSize: 26,
    lineHeight: 32,
    fontWeight: "400",
    color: theme.text,
    letterSpacing: -0.5,
    textAlign: "center",
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 20,
    color: theme.muted,
    textAlign: "center",
    marginTop: 6,
    marginBottom: 20,
  },
  label: { fontSize: 14, fontWeight: "600", color: theme.text, marginBottom: 6 },
  input: {
    height: 46,
    borderWidth: 1.5,
    borderColor: theme.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    fontSize: 16,
    color: theme.text,
    backgroundColor: theme.field,
    marginBottom: 14,
  },
  inputFocused: { borderColor: theme.cyan },
  passwordInput: { paddingRight: 64 },
  toggle: { position: "absolute", right: 14, top: 0, height: 46, justifyContent: "center" },
  toggleText: { fontSize: 14, fontWeight: "600", color: theme.cyan },
  error: { fontSize: 14, color: theme.error, marginBottom: 12, lineHeight: 20 },
  notice: { fontSize: 14, color: theme.mint, marginBottom: 12, lineHeight: 20 },
  buttonWrap: { marginTop: 4, borderRadius: 999, overflow: "hidden" },
  button: { height: 50, alignItems: "center", justifyContent: "center" },
  buttonText: { color: theme.onGradient, fontSize: 16, fontWeight: "700" },
  passkeyButton: {
    height: 46,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.cyan,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 12,
    backgroundColor: "transparent",
  },
  passkeyButtonText: { color: theme.cyan, fontSize: 14, fontWeight: "600" },
  switch: { alignItems: "center", paddingVertical: 14 },
  switchText: { fontSize: 14, color: theme.cyan, fontWeight: "600" },
});