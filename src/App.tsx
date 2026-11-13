import { useState } from "react";
import { PlayIcon, PlusIcon } from "./components/icons";
import { ProjectList } from "./components/ProjectList";
import type { ScanStatus } from "./lib/tauri";
import { mockProjects, mockStatuses } from "./mock";

function App() {
  // Hito 1: estado de prueba solo para ver los estados de fila.
  // En el Hito 3 esto lo manda Rust por el evento `scan://status`.
  const [statuses, setStatuses] = useState<Record<string, ScanStatus>>(mockStatuses);
  const projects = mockProjects;

  const scan = (id: string) =>
    setStatuses((s) => ({ ...s, [id]: { id, state: "running", step: 1, totalSteps: 3, label: "Preparando" } }));

  const cancel = (id: string) =>
    setStatuses((s) => {
      const { [id]: _removed, ...rest } = s;
      return rest;
    });

  return (
    <div className="page">
      <header className="header">
        <div className="header__title">
          <h1>Proyectos</h1>
          <span className="status">
            <span className="status__dot" aria-hidden="true" />
            SonarQube en línea, {projects.length} proyectos
          </span>
        </div>
        <div className="header__actions">
          <button type="button" className="btn btn--outlined btn--icon">
            <PlusIcon />
            Agregar
          </button>
          <button type="button" className="btn btn--filled btn--icon">
            <PlayIcon />
            Escanear todos
          </button>
        </div>
      </header>

      <ProjectList projects={projects} statuses={statuses} onScan={scan} onCancel={cancel} />

      <p className="footnote">
        Los proyectos se escanean uno a la vez. El resultado aparece en SonarQube unos segundos después de terminar.
      </p>
    </div>
  );
}

export default App;
