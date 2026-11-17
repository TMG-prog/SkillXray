const staticConfig = require("./app.json");

module.exports = ({ config }) => ({
  ...staticConfig.expo,
  ...config,
  extra: {
    ...staticConfig.expo.extra,
    ...config.extra,
    apiUrl: process.env.EXPO_PUBLIC_API_URL,
    useMockAnalysis: process.env.EXPO_PUBLIC_USE_MOCK_ANALYSIS === "1",
  },
});
