import type { ScanState } from "../lib/tauri";
import { PlayIcon, Spinner } from "./icons";

interface Props {
  name: string;
  scanState?: ScanState;
  onScan: () => void;
  onCancel: () => void;
}

/** Botón de la fila: Escanear, o indicador + Cancelar/Quitar si está activo. */
export function ScanButton({ name, scanState, onScan, onCancel }: Props) {
  if (scanState === "running") {
    return (
      <div className="row-actions">
        <Spinner />
        <button type="button" className="btn btn--outlined" onClick={onCancel} aria-label={`Cancelar escaneo de ${name}`}>
          Cancelar
        </button>
      </div>
    );
  }
  if (scanState === "queued") {
    return (
      <button type="button" className="btn btn--outlined" onClick={onCancel} aria-label={`Quitar ${name} de la cola`}>
        Quitar
      </button>
    );
  }
  return (
    <button type="button" className="btn btn--tonal" onClick={onScan} aria-label={`Escanear ${name}`}>
      <PlayIcon />
      Escanear
    </button>
  );
}
