import type { Gate, ScanState } from "../lib/tauri";
import { AlertIcon, CheckIcon, ClockIcon, CrossIcon } from "./icons";

interface Props {
  gate: Gate;
  /** Si hay un escaneo activo o fallido, el chip muestra eso en vez del gate. */
  scanState?: ScanState;
}

/** Chip de estado. Nunca solo color: siempre ícono o contorno. */
export function GateChip({ gate, scanState }: Props) {
  if (scanState === "running") return <span className="chip chip--run">Escaneando</span>;
  if (scanState === "queued")
    return (
      <span className="chip chip--outline chip--icon">
        <ClockIcon />
        En cola
      </span>
    );
  if (scanState === "error")
    return (
      <span className="chip chip--fail chip--icon">
        <AlertIcon />
        Error
      </span>
    );

  switch (gate) {
    case "pass":
      return (
        <span className="chip chip--pass chip--icon">
          <CheckIcon />
          Aprobado
        </span>
      );
    case "fail":
      return (
        <span className="chip chip--fail chip--icon">
          <CrossIcon />
          No aprobado
        </span>
      );
    default:
      return <span className="chip chip--outline">Sin análisis</span>;
  }
}
