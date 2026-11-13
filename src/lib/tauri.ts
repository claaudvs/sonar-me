// Única puerta de entrada a Tauri desde React.
// Aquí irán los `invoke` a los comandos de Rust y los `listen` a sus eventos.
// Los tipos deben coincidir con los de Rust (ver CLAUDE.md).

export type ScanState = "queued" | "running" | "ok" | "error" | "cancelled";

/** Payload del evento `scan://status`. `step` empieza en 1. */
export interface ScanStatus {
  id: string;
  state: ScanState;
  step: number;
  totalSteps: number;
  label: string;
}

/** Payload del evento `scan://log` (línea ya enmascarada). */
export interface ScanLogLine {
  id: string;
  line: string;
}

export type Gate = "pass" | "fail" | "none";

/** Lo que la lista necesita de cada proyecto. */
export interface ProjectView {
  id: string;
  name: string;
  gate: Gate;
  /** Fecha ISO del último análisis, o null si nunca se escaneó. */
  lastScan: string | null;
}
