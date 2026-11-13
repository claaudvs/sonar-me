import type { ProjectView, ScanStatus } from "../lib/tauri";
import { formatDate } from "../lib/format";
import { GateChip } from "./GateChip";
import { ScanButton } from "./ScanButton";

interface Props {
  project: ProjectView;
  status?: ScanStatus;
  onScan: (id: string) => void;
  onCancel: (id: string) => void;
}

function subtitle(project: ProjectView, status?: ScanStatus): string {
  switch (status?.state) {
    case "running":
      return `${status.label}, paso ${status.step} de ${status.totalSteps}`;
    case "queued":
      return "En cola, empieza cuando termine el escaneo actual";
    case "error":
      return status.label ? `Falló: ${status.label.toLowerCase()}, paso ${status.step} de ${status.totalSteps}` : "Falló el escaneo";
    default:
      return project.lastScan ? `Último escaneo: ${formatDate(project.lastScan)}` : "Nunca escaneado";
  }
}

export function ProjectRow({ project, status, onScan, onCancel }: Props) {
  const state = status?.state;
  const running = status?.state === "running" ? status : undefined;
  const progress = running && running.totalSteps > 0 ? (running.step / running.totalSteps) * 100 : 0;

  return (
    <li className="row">
      <div className="row__main">
        <div className="row__text">
          <div className="row__title">
            <span className="row__name">{project.name}</span>
            <GateChip gate={project.gate} scanState={state} />
          </div>
          <span className={state === "error" ? "row__sub row__sub--error" : "row__sub"}>{subtitle(project, status)}</span>
        </div>
        <ScanButton
          name={project.name}
          scanState={state}
          onScan={() => onScan(project.id)}
          onCancel={() => onCancel(project.id)}
        />
      </div>
      {running && (
        <div
          className="progress"
          role="progressbar"
          aria-label={`Progreso de ${project.name}`}
          aria-valuemin={0}
          aria-valuemax={running.totalSteps}
          aria-valuenow={running.step}
        >
          <div className="progress__bar" style={{ width: `${progress}%` }} />
        </div>
      )}
    </li>
  );
}
