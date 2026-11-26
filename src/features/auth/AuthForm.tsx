import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, TouchableOpacity, View, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import { makeRedirectUri } from 'expo-auth-session';
import { useRouter } from 'expo-router';
import { supabase } from '../../lib/supabase'; // Adjust path to your supabase client
import { brand } from '../../components/ui/theme';

WebBrowser.maybeCompleteAuthSession();

export const theme = {
  ...brand,
  card: brand.surface,
  subText: brand.muted,
} as const;


export default function AuthForm() {
  const router = useRouter();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  // Email / Password Auth
  const handleAuth = async () => {
    if (!email || !password || (!isLogin && !confirmPassword)) {
      Alert.alert('Error', 'Please fill in all fields.');
      return;
    }

    if (!isLogin && password !== confirmPassword) {
      Alert.alert('Error', "The passwords don't match.");
      return;
    }

    setLoading(true);
    try {
      if (isLogin) {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        Alert.alert('Success', 'Check your email for confirmation link if required!');
      }
    } catch (error: any) {
      Alert.alert('Authentication Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  // Google Auth Handler
  const handleGoogleAuth = async () => {
    try {
      const redirectTo = makeRedirectUri({ scheme: 'skillxray' }); 

      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo,
          skipBrowserRedirect: true,
        },
      });

      if (error) throw error;
      if (!data?.url) return;

      // Open browser for Google OAuth flow
      const res = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
      
      if (res.type === 'success' && res.url) {
        // Extract tokens from result URL and set session
        const urlParams = new URLSearchParams(res.url.split('#')[1] || res.url.split('?')[1]);
        const access_token = urlParams.get('access_token');
        const refresh_token = urlParams.get('refresh_token');

        if (access_token && refresh_token) {
          await supabase.auth.setSession({ access_token, refresh_token });
        }
      }
    } catch (error: any) {
      Alert.alert('Google Sign-In Error', error.message);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{isLogin ? 'Welcome Back' : 'Create Account'}</Text>
      <Text style={styles.subtitle}>
        {isLogin ? 'Sign in to access your account' : 'Sign up to get started'}
      </Text>

      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor={theme.subText}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor={theme.subText}
          value={password}
          onChangeText={setPassword}
          autoCapitalize="none"
          textContentType={isLogin ? 'password' : 'newPassword'}
          autoComplete={isLogin ? 'current-password' : 'new-password'}
          secureTextEntry
        />
        {!isLogin && (
          <TextInput
            style={styles.input}
            placeholder="Confirm Password"
            placeholderTextColor={theme.subText}
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            autoCapitalize="none"
            textContentType="newPassword"
            autoComplete="new-password"
            secureTextEntry
            accessibilityLabel="Confirm password"
          />
        )}
        {isLogin && (
          <TouchableOpacity
            onPress={() => router.push('/forgot-password')}
            style={styles.forgotPassword}
            accessibilityRole="button"
          >
            <Text style={styles.forgotPasswordText}>Forgot password?</Text>
          </TouchableOpacity>
        )}
      </View>

      <TouchableOpacity 
        style={[styles.primaryButton, loading && { opacity: 0.7 }]} 
        onPress={handleAuth} 
        disabled={loading}
        activeOpacity={0.8}
      >
        <Text style={styles.primaryButtonText}>
          {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Sign Up')}
        </Text>
      </TouchableOpacity>

      <View style={styles.dividerContainer}>
        <View style={styles.line} />
        <Text style={styles.orText}>or continue with</Text>
        <View style={styles.line} />
      </View>

      <View style={styles.socialRow}>
        <TouchableOpacity style={styles.socialButton} onPress={handleGoogleAuth} activeOpacity={0.8}>
          <Ionicons name="logo-google" size={18} color={theme.text} style={styles.icon} />
          <Text style={styles.socialButtonText}>Google</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity
        onPress={() => {
          setIsLogin((current) => !current);
          setConfirmPassword('');
        }}
        style={styles.switchContainer}
      >
        <Text style={styles.switchText}>
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <Text style={styles.switchTextBold}>{isLogin ? 'Sign Up' : 'Sign In'}</Text>
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { width: '100%', maxWidth: 400, alignItems: 'center' },
  title: { fontSize: 28, fontWeight: '700', color: theme.text, marginBottom: 8 },
  subtitle: { fontSize: 14, color: theme.subText, marginBottom: 32 },
  inputContainer: { width: '100%', gap: 16, marginBottom: 20 },
  forgotPassword: { alignSelf: 'flex-end', marginTop: -8, paddingVertical: 4 },
  forgotPasswordText: { color: theme.cyan, fontSize: 14, fontWeight: '600' },
  input: {
    width: '100%',
    backgroundColor: theme.card,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: theme.text,
    fontSize: 15,
  },
  primaryButton: {
    width: '100%',
    backgroundColor: theme.cyan,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 24,
  },
  primaryButtonText: { color: theme.onGradient, fontSize: 16, fontWeight: '700' },
  dividerContainer: { flexDirection: 'row', alignItems: 'center', width: '100%', marginBottom: 20 },
  line: { flex: 1, height: 1, backgroundColor: theme.border },
  orText: { color: theme.subText, paddingHorizontal: 12, fontSize: 12 },
  socialRow: { flexDirection: 'row', width: '100%', gap: 12, marginBottom: 24 },
  socialButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.card,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 12,
    paddingVertical: 12,
  },
  icon: { marginRight: 8 },
  socialButtonText: { color: theme.text, fontSize: 14, fontWeight: '600' },
  switchContainer: { padding: 8 },
  switchText: { color: theme.subText, fontSize: 14 },
  switchTextBold: { color: theme.cyan, fontWeight: '600' },
});