# SkillXray — Mobile (Expo)

React Native app for SkillXray, built with Expo + Expo Router, talking to the
same Supabase backend as the web version.

## Run it on your phone with Expo Go

```bash
npm install
npx expo start
```

This prints a QR code in the terminal (and opens a page at localhost:8081).

- **Android**: open the **Expo Go** app (install from Play Store) and tap
  "Scan QR code".
- **iPhone**: open the regular **Camera** app and point it at the QR code —
  it'll prompt you to open in Expo Go (install from the App Store first).

**Your phone and your computer must be on the same Wi-Fi network.** If it
won't connect (common on restrictive/campus/office Wi-Fi), run:

```bash
npx expo start --tunnel
```

which routes through Expo's relay instead of relying on local network
discovery — slower, but works almost anywhere.

## Structure

```
skillxray-mobile/
├── app/                        Expo Router — file path = screen route
│   ├── _layout.tsx               root stack: login vs. authenticated tabs
│   ├── login.tsx                 sign-in screen
│   └── (tabs)/                   authenticated area, bottom tab bar
│       ├── _layout.tsx             tab navigator
│       ├── dashboard.tsx           Career Readiness Index
│       ├── resume-upload.tsx       resume + target role
│       ├── skill-analysis.tsx      skill gap report
│       └── recommendations.tsx     ranked learning resources
├── src/
│   ├── features/                 same pipeline-stage folders as the web app
│   ├── components/layout, ui/    shared UI (empty for now)
│   ├── lib/supabase.ts            Supabase client w/ AsyncStorage session persistence
│   ├── services/                 Supabase queries, one file per resource
│   ├── types/index.ts             mirrors the ER diagram
│   └── hooks/
├── assets/                      app icon, splash image (add your own)
├── app.json                     Expo app config
├── babel.config.js
├── tsconfig.json
└── .env                         EXPO_PUBLIC_SUPABASE_URL / EXPO_PUBLIC_SUPABASE_ANON_KEY (pre-filled)
```

## Notes
- Expo requires client-exposed env vars to be prefixed `EXPO_PUBLIC_` (unlike
  Vite's `VITE_` prefix) — that's already set up in `.env`.
- `expo-document-picker` is wired into the resume upload screen as a starting
  point; the actual upload-to-Supabase-Storage call is a TODO.
- Routing here is file-based (a screen's route comes from its file path under
  `app/`), unlike the web app's explicit `AppRoutes.tsx` route table.
