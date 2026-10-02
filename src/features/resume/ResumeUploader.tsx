import { View, Text, Button, StyleSheet, Alert } from "react-native";
import * as DocumentPicker from "expo-document-picker";

// Handles resume upload + target career path selection (feeds the NLP/Feature
// Extraction module described in the proposal).
export function ResumeUploader() {
  async function pickResume() {
    const result = await DocumentPicker.getDocumentAsync({
      type: ["application/pdf", "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    });
    if (result.canceled) return;
    // TODO: upload result.assets[0] to Supabase Storage
    Alert.alert("Selected", result.assets[0].name);
  }

  return (
    <View style={styles.section}>
      <Text style={styles.title}>Upload your resume</Text>
      <Button title="Choose file" onPress={pickResume} />
      {/* TODO: target role select -> JobRoles table */}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { padding: 16 },
  title: { fontSize: 20, fontWeight: "600", marginBottom: 16 },
});
