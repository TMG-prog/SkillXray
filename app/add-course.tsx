import { Stack } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { AddCourseForm } from "@/features/course-tracker/addcourseform";
import { brand } from "@/components/ui/brand";

export default function AddCourseScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: brand.bg }} edges={["top"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <AddCourseForm />
    </SafeAreaView>
  );
}