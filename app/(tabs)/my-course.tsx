import { ScrollView } from "react-native";
import { CourseTracker } from "@/features/course-tracker/CourseTracker";
import { brand } from "@/components/ui/brand";

export default function MyCoursesScreen() {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: brand.bg }}>
      <CourseTracker />
    </ScrollView>
  );
}