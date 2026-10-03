import { Platform } from "react-native";
import { supabase } from "@/lib/supabase";

/**
 * Create an account. The full name goes in as user metadata so the
 * database trigger can copy it into `profiles`.
 *
 * With email confirmation on, there is no session yet: needsConfirmation is true.
 */
export async function signUpWithEmail(email: string, password: string, fullName: string) {
  const { data, error } = await supabase.auth.signUp({
    email: email.trim(),
    password,
    options: { data: { full_name: fullName.trim() } },
  });

  if (error) return { success: false as const, error: error.message };
  return {
    success: true as const,
    user: data.user,
    needsConfirmation: !data.session,
  };
}

/**
 * Register a passkey for the signed-in user.
 * The JS client runs the WebAuthn ceremony through the browser, so this works
 * on web only. Native needs a native passkey library plus the lower-level
 * supabase.auth.passkey API.
 */
export async function registerDevicePasskey() {
  if (Platform.OS !== "web") {
    return { success: false as const, error: "Passkeys aren't supported in the mobile app yet." };
  }

  const { data: { session } } = await supabase.auth.getSession();
  if (!session) {
    return { success: false as const, error: "Sign in first, then add a passkey." };
  }

  try {
    const { data, error } = await supabase.auth.registerPasskey();
    if (error) throw error;
    return { success: true as const, passkeyId: data.id };
  } catch (error: any) {
    return { success: false as const, error: error.message ?? "Passkey registration failed." };
  }
}