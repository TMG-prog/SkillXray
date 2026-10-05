import { ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { CourseTracker } from "@/features/course-tracker/CourseTracker";
import { brand } from "@/components/ui/brand";

export default function MyCoursesScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: brand.bg }} edges={["top"]}>
      <ScrollView style={{ flex: 1 }}>
        <CourseTracker />
      </ScrollView>
    </SafeAreaView>
  );
}