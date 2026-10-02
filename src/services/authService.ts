import { supabase } from '../lib/supabase';

/**
 * Step 1: Create a base user account using email and password.
 */
export async function signUpWithEmail(email: string, pass: string) {
  try {
    const { data, error } = await supabase.auth.signUp({
      email: email,
      password: pass,
    });

    if (error) throw error;
    return { success: true, user: data.user };
  } catch (error: any) {
    console.error('Sign up failed:', error.message);
    return { success: false, error: error.message };
  }
}

/**
 * Step 2: Register a biometric passkey (Face ID / Touch ID) for the active user session.
 * Must be called immediately after a user is signed in.
 */
export async function registerDevicePasskey() {
  try {
    const { data, error } = await supabase.auth.registerPasskey();

    if (error) throw error;

    console.log('Passkey successfully registered ID:', data.id);
    return { success: true, passkeyId: data.id };
  } catch (error: any) {
    console.error('Passkey registration error:', error.message);
    return { success: false, error: error.message };
  }
}