import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";
import { RecommendationList } from "@/features/recommendations/RecommendationList";
import { brand, SERIF } from "@/components/ui/brand";

export default function RecommendationsScreen() {
  return (
    <View style={styles.root}>
      <LinearGradient
        colors={["rgba(37,217,208,0.22)", "rgba(37,217,208,0)"]}
        style={styles.glow}
        pointerEvents="none"
      />
      <SafeAreaView style={styles.safeArea} edges={["top"]}>
        <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
          <View style={styles.header}>
            <Text style={styles.title}>Recommended for you</Text>
            <Text style={styles.subtitle}>
              Courses and resources that close the gaps in your skills.
            </Text>
          </View>
          <RecommendationList />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: brand.bg },
  safeArea: { flex: 1 },
  glow: { position: "absolute", top: 0, left: 0, right: 0, height: 320 },
  container: { padding: 16, paddingBottom: 40 },
  header: { marginTop: 16, marginBottom: 24 },
  title: {
    fontFamily: SERIF,
    fontSize: 32,
    lineHeight: 37,
    fontWeight: "400",
    letterSpacing: -0.5,
    color: brand.text,
  },
  subtitle: { fontSize: 15, lineHeight: 21, color: brand.muted, marginTop: 8 },
});