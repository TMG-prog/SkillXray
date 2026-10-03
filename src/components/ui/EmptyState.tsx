import { View, Text, Pressable, StyleSheet } from "react-native";
import { Feather } from "@expo/vector-icons";
import { brand, SERIF } from "./brand";

interface Props {
  icon: keyof typeof Feather.glyphMap;
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ icon, title, message, actionLabel, onAction }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.iconCircle}>
        <Feather name={icon} size={26} color="#25D9D0" />
      </View>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.message}>{message}</Text>
      {actionLabel && onAction && (
        <Pressable style={styles.button} onPress={onAction}>
          <Text style={styles.buttonText}>{actionLabel}</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: "center", paddingVertical: 48, paddingHorizontal: 24 },
  iconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "rgba(37,217,208,0.12)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  title: { fontFamily: SERIF, fontSize: 20, color: brand.text, textAlign: "center", marginBottom: 8 },
  message: { fontSize: 14, lineHeight: 20, color: brand.muted, textAlign: "center", marginBottom: 20 },
  button: { backgroundColor: "#25D9D0", borderRadius: 999, paddingVertical: 12, paddingHorizontal: 24 },
  buttonText: { color: "#06201F", fontWeight: "700", fontSize: 14 },
});