import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import AuthForm, { theme } from "./AuthForm";

const DOME = 700;

export default function LoginScreen() {
  const { width, height } = useWindowDimensions();

  return (
    <View style={styles.root}>
      {/* Glow: a gradient band at the bottom, mostly covered by a dark dome so only the rim shows */}
      <LinearGradient
        colors={["transparent", "#0C6F68", theme.cyan, theme.mint]}
        locations={[0, 0.35, 0.7, 1]}
        style={[styles.glow, { top: height * 0.55 }]}
        pointerEvents="none"
      />
      <View
        pointerEvents="none"
        style={[
          styles.dome,
          { left: (width - DOME) / 2, top: height * 0.68 },
        ]}
      />

      <KeyboardAvoidingView
        style={styles.fill}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          <AuthForm />
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.bg, overflow: "hidden" },
  fill: { flex: 1 },
  glow: { position: "absolute", left: 0, right: 0, bottom: 0 },
  dome: {
    position: "absolute",
    width: DOME,
    height: DOME,
    borderRadius: DOME / 2,
    backgroundColor: theme.bg,
  },
  content: { flexGrow: 1, alignItems: "center", justifyContent: "center", padding: 20 },
});