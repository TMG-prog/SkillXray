import { useEffect, useState } from "react";
import { Stack } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { AppDataProvider } from "@/state/appdatacontext";

export default function RootLayout() {
  const [session, setSession] = useState<Session | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        setSession(nextSession);
        setIsReady(true); // INITIAL_SESSION fires first, so getSession() isn't needed
      }
    );
    return () => subscription.unsubscribe();
  }, []);

  if (!isReady) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#03110F" }}>
        <ActivityIndicator size="large" color="#25D9D0" />
      </View>
    );
  }

  return (
    <AppDataProvider>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Protected guard={!!session}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen
            name="resume-upload"
            options={{
              presentation: "modal",
              headerShown: true,
              title: "Upload Resume",
              headerStyle: { backgroundColor: "#03110F" },
              headerTintColor: "#EEF7F4",
            }}
          />
          <Stack.Screen
            name="add-course"
            options={{
              presentation: "modal",
              headerShown: true,
              title: "Add a Course",
              headerStyle: { backgroundColor: "#03110F" },
              headerTintColor: "#EEF7F4",
            }}
          />
        </Stack.Protected>

        <Stack.Protected guard={!session}>
          <Stack.Screen name="login" />
        </Stack.Protected>
      </Stack>
    </AppDataProvider>
  );
}