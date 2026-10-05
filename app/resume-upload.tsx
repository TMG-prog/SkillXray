import { ScrollView, StyleSheet, View } from "react-native";
import { ResumeUploader } from "@/features/resume/ResumeUploader";
import { brand } from "@/components/ui/brand";

export default function ResumeUploadScreen() {
  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={styles.container}>
        <ResumeUploader />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: brand.bg },
  container: { paddingBottom: 40 },
});
