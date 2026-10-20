import { Tabs } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { brand } from "@/components/ui/theme";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: brand.cyan,
        tabBarInactiveTintColor: brand.muted,
        tabBarStyle: {
          backgroundColor: brand.surfaceSolid,
          borderTopColor: brand.border,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Home", tabBarIcon: ({ color, size }) => <Feather name="home" color={color} size={size} /> }}
      />
      <Tabs.Screen
        name="courses"
        options={{ title: "Recommended", tabBarIcon: ({ color, size }) => <Feather name="star" color={color} size={size} /> }}
      />
      <Tabs.Screen
        name="analysis"
        options={{ title: "Analysis", tabBarIcon: ({ color, size }) => <Feather name="crop" color={color} size={size} /> }}
      />
      <Tabs.Screen
        name="my-course"
        options={{ title: "My Courses", tabBarIcon: ({ color, size }) => <Feather name="book" color={color} size={size} /> }}
      />
    </Tabs>
  );
}