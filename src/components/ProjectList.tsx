import type { ProjectView, ScanStatus } from "../lib/tauri";
import { ProjectRow } from "./ProjectRow";

interface Props {
  projects: ProjectView[];
  statuses: Record<string, ScanStatus>;
  onScan: (id: string) => void;
  onCancel: (id: string) => void;
}

export function ProjectList({ projects, statuses, onScan, onCancel }: Props) {
  return (
    <ul className="list">
      {projects.map((p) => (
        <ProjectRow key={p.id} project={p} status={statuses[p.id]} onScan={onScan} onCancel={onCancel} />
      ))}
    </ul>
  );
}
