import { Platform } from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { createPdf } from "pdfmake/build/pdfmake";
import fonts from "pdfmake/build/vfs_fonts";
import type { Analysis } from "@/state/appdatacontext";
import { buildAnalysisReport } from "./analysisReport";

export async function downloadAnalysisReport(analysis: Analysis): Promise<void> {
  const filename = `skillxray-${analysis.targetRole.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 50) || "analysis"}.pdf`;
  const pdf = createPdf(buildAnalysisReport(analysis, new Date()), undefined, undefined, fonts);

  if (Platform.OS === "web") {
    const blob = await new Promise<Blob>((resolve) => pdf.getBlob(resolve));
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    }
    return;
  }

  if (!await Sharing.isAvailableAsync()) {
    throw new Error("Sharing is unavailable on this device.");
  }
  if (!FileSystem.cacheDirectory) {
    throw new Error("The app's temporary file directory is unavailable.");
  }
  const base64 = await new Promise<string>((resolve) => pdf.getBase64(resolve));
  const uri = `${FileSystem.cacheDirectory}${filename}`;
  await FileSystem.writeAsStringAsync(uri, base64, { encoding: FileSystem.EncodingType.Base64 });
  await Sharing.shareAsync(uri, {
    mimeType: "application/pdf",
    UTI: "com.adobe.pdf",
    dialogTitle: "Save or share your analysis report",
  });
}
