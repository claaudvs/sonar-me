// Datos de prueba del Hito 1. Se reemplazan por Rust en el Hito 2.
import type { ProjectView, ScanStatus } from "./lib/tauri";

export const mockProjects: ProjectView[] = [
  { id: "bff", name: "Back Process BFF", gate: "pass", lastScan: "2026-11-06T10:42:00" },
  { id: "web", name: "Back Process Web Client", gate: "pass", lastScan: "2026-11-06T10:15:00" },
  { id: "risk", name: "Credit Risk Assessment", gate: "fail", lastScan: "2026-11-13T18:02:00" },
  { id: "bum", name: "BUM", gate: "none", lastScan: null },
  { id: "api", name: "Payments API", gate: "pass", lastScan: "2026-11-12T09:30:00" },
];

export const mockStatuses: Record<string, ScanStatus> = {
  bum: { id: "bum", state: "running", step: 2, totalSteps: 3, label: "Compilando" },
  api: { id: "api", state: "queued", step: 0, totalSteps: 0, label: "" },
  risk: { id: "risk", state: "error", step: 2, totalSteps: 3, label: "Compilando" },
};
