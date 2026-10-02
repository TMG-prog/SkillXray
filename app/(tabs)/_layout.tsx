import { Tabs } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { useColorScheme } from "react-native";
import { colors } from "@/components/ui/theme";

export default function TabsLayout() {
  const colorScheme = useColorScheme();
  const themeColors = colors[colorScheme === "dark" ? "dark" : "light"];

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: themeColors.textPrimary,
        tabBarInactiveTintColor: themeColors.textMuted,
        tabBarStyle: {
          backgroundColor: themeColors.surface,
          borderTopColor: themeColors.border,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Home", tabBarIcon: ({ color, size }) => <Feather name="home" color={color} size={size} /> }}
      />
      <Tabs.Screen
        name="courses"
        options={{ title: "Courses", tabBarIcon: ({ color, size }) => <Feather name="book-open" color={color} size={size} /> }}
      />
      <Tabs.Screen
        name="analysis"
        options={{ title: "Analysis", tabBarIcon: ({ color, size }) => <Feather name="crop" color={color} size={size} /> }}
      />
    </Tabs>
  );
}