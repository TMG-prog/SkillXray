# SkillXray

SkillXray is a mobile app that shows job seekers where their skills stand. Upload your resume, see how ready you are for your target roles, and get tailored recommendations for closing the gaps. Keep track of your progress.

## Features

- **Email and password sign-in** with Supabase Auth, and sessions that persist across app restarts
- **Resume upload** to start a skill analysis
- **Skill gap analysis** with a career readiness score and a list of gaps by severity
- **Recommendations** for courses and resources matched to each gap

## Tech stack

- [Expo](https://expo.dev) and React Native, written in TypeScript
- [Expo Router](https://docs.expo.dev/router/introduction/) for file-based navigation
- [Supabase](https://supabase.com) for authentication
- `expo-linear-gradient` and `react-native-svg` for the gradient UI and score ring

## Getting started

### Prerequisites

- Node.js (LTS)
- A Supabase project
- The Expo Go app, or an iOS simulator or Android emulator

### Install

```bash
npm install
npx expo install expo-linear-gradient react-native-svg @react-native-async-storage/async-storage
npm install @supabase/supabase-js react-native-url-polyfill
```

### Configure environment variables

Copy `.env.example` to `.env` and fill in your project values (Supabase dashboard, Project Settings, API):

```bash
EXPO_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=YOUR-ANON-PUBLIC-KEY
```

Only the public anon key belongs in the app. Never put the service role key in this project. Restart Expo after changing `.env`.

### Configure Supabase Auth

In the Supabase dashboard under Authentication:

- While developing, you can turn off **Confirm email** so new accounts can sign in straight away. Turn it back on before release.
- Set the minimum password length to 8 to match the app's sign-up check.

### Run

```bash
npx expo start
```

Then press `i` for iOS, `a` for Android, or scan the QR code with Expo Go.

## Project structure

```
app/
  _layout.tsx          Root layout: AuthProvider and the signed-in/signed-out redirect
  login.tsx            Login route
  ...                  Home, analysis, courses and resume-upload routes
components/
  AuthForm.tsx         Email/password form (sign in and sign up)
  LoginScreen.tsx      Login screen background and layout
  ui/
    brand.ts           Shared colors and fonts
features/
  recommendations/     Recommendation list
lib/
  supabase.ts          Supabase client with session persistence
providers/
  AuthProvider.tsx     Session state, useAuth() hook and signOut
```

## How authentication works

1. `lib/supabase.ts` creates the Supabase client and stores the session in AsyncStorage.
2. `AuthProvider` reads the stored session on launch and listens for changes with `onAuthStateChange`.
3. `AuthGate` in `app/_layout.tsx` redirects signed-out users to `/login` and signed-in users to the home screen.
4. Screens read the current user and call `signOut()` through `useAuth()`.

```tsx
const { session, signOut } = useAuth();
```

## Design

The app uses a dark teal theme with cyan-to-mint gradients on buttons and progress bars. The palette and serif heading font live in `components/ui/brand.ts`.

## Status

Under active development.

- Sign-in, sign-up and session persistence are implemented.
- The analysis scores and gaps, and the recommendation list, currently use placeholder data.
- Resume upload and the analysis backend are not connected yet.

## Scripts

| Command | What it does |
| --- | --- |
| `npx expo start` | Start the dev server |
| `npx expo start -c` | Start with a cleared cache |
| `npx tsc --noEmit` | Type-check the project |

## License


