import { View, ScrollView, StyleSheet } from "react-native";
import { ResumeUploader } from "@/features/resume/ResumeUploader";
import { spacing } from "@/components/ui/theme";

export default function ResumeUploadScreen() {
  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View>
        <ResumeUploader />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({ container: { padding: 16 } });
