# Sonar Local

App de escritorio (Windows y macOS) para escanear proyectos locales en un
SonarQube que corre en Docker (`http://localhost:9000`) con un solo clic.
Muestra una lista de proyectos con su quality gate, la fecha del último
escaneo y un botón Escanear. Permite agregar proyectos eligiendo su carpeta.

## Stack

- **Tauri v2**. Backend en Rust (`src-tauri/`), frontend en
  **React + TypeScript + Vite** (`src/`).
- Plugins oficiales: `dialog` (elegir carpeta), `store` (registro de
  proyectos), `opener` (abrir el dashboard de Sonar), `notification`
  (aviso al terminar un escaneo), `single-instance`.
- Crates: `tokio` (procesos y async), `reqwest` (API de SonarQube),
  `serde`, `command-group` (matar árbol de procesos), `fix-path-env` (PATH en macOS).

## Arquitectura

- **Rust es la fuente de verdad.** React solo muestra lo que llega de Rust
  y pide acciones con `invoke`. No dupliques estado de negocio en React.
- Comandos (`#[tauri::command]`): `list_projects`, `inspect_folder`,
  `add_project`, `remove_project`, `suggest_projects`, `get_settings`,
  `save_settings`, `check_tools`, `scan_project`, `scan_all`,
  `cancel_scan`, `scan_log`, `sonar_status`, `sonar_create_project`.
- Eventos de Rust a la interfaz (mismos tipos en Rust y en `src/lib/tauri.ts`):
  - `scan://status` → `{ id, state, step, totalSteps, label }`, con
    `state` = `queued | running | ok | error | cancelled`; `step` empieza en 1.
  - `scan://log` → `{ id, line }` (una línea ya enmascarada).
  Rust guarda también el log del último escaneo de cada proyecto en memoria
  para que `scan_log(id)` lo entregue al abrir el panel de log.
- Configuración (`workspace`, `sonarUrl`, `tokenFile`, opcionales `javaHome`
  y `scannerBin`) en el plugin `store`. Nada específico de una empresa
  (prefijos de carpetas, rutas personales) va en el código.
- Toda llamada a Tauri desde React pasa por `src/lib/tauri.ts`.

## Reglas que no se negocian

- **El token de SonarQube nunca llega al frontend.** Se lee en Rust
  (`~/.sonar/token` o variable `SONAR_TOKEN`) y se oculta como `****` en el log.
- **Un escaneo a la vez.** Cola FIFO en Rust; los demás quedan "en cola".
  Un proyecto que ya está en cola o escaneándose no se vuelve a encolar.
- **Sin shell.** Ejecuta los programas directamente con argumentos
  (`tokio::process::Command`), nunca `sh -c` ni `cmd /c` con strings
  armados. Nada de `rm -rf`: usa `std::fs::remove_dir_all`.
  Excepción conocida: en Windows Rust ejecuta `sonar-scanner.bat` a través
  de `cmd.exe` por dentro. Es aceptable (Rust ≥ 1.77.2 escapa los argumentos);
  no lo reemplaces por un `cmd /c` armado a mano.
- **Multiplataforma siempre.** Rutas con `PathBuf`; en Windows el escáner
  JS es `sonar-scanner.bat`, Java es `java.exe`. Código específico con
  `#[cfg(target_os = "...")]`.
- **PATH en macOS:** una app abierta desde Finder no hereda el PATH de la
  terminal. Llama a `fix_path_env::fix()` al iniciar y agrega
  explícitamente `~/.dotnet/tools`, `/usr/local/share/dotnet`,
  `/opt/homebrew/bin` y `/usr/local/bin` (sin duplicar entradas).
- **Cancelar mata el árbol completo** (`dotnet build` lanza hijos): usa
  `command-group`.

## Cómo se escanea (portar desde `docs/referencia/prototipo_python.py`)

Proyecto **.NET** (tiene `.sln`, `.slnx` o `.csproj`), en la carpeta del proyecto:
1. Borrar `.sonarqube`.
2. `dotnet-sonarscanner begin /k:<clave> /n:<nombre> /d:sonar.host.url=<url> /d:sonar.token=<token> /d:sonar.scanner.javaExePath=<java>`
3. `dotnet build [<solucion>] --no-incremental -nodeReuse:false -p:WarningLevel=0`
   (`<solucion>` es el primer `.sln`/`.slnx` en orden alfabético; si solo hay
   `.csproj`, sin argumento. `-nodeReuse:false` evita que queden procesos de
   MSBuild vivos bloqueando `.sonarqube` o sobreviviendo a un cancelar).
4. `dotnet-sonarscanner end /d:sonar.token=<token>`
5. Borrar `.sonarqube` (también si algo falló).

Proyecto **JS/TS** (tiene `package.json`):
1. `sonar-scanner -Dsonar.projectKey=<clave> -Dsonar.projectName=<nombre> -Dsonar.sources=<src> -Dsonar.host.url=<url> -Dsonar.exclusions=**/node_modules/**,**/__test__/**,**/.next/**,**/public/**,**/*.test.*,**/*.spec.* -Dsonar.javascript.node.maxspace=4096`
   con `JAVA_HOME` apuntando al Java detectado y el token en la variable de
   entorno `SONAR_TOKEN` (no como argumento, para que no se vea con `ps`).
   `<src>` = `src` si esa carpeta existe; si no, `.`.
2. Borrar `.scannerwork` (también si algo falló).

Riesgo aceptado: en .NET el token va como argumento `/d:sonar.token` y es
visible en la lista de procesos mientras corre el escaneo.

Si un paso termina con código ≠ 0 o no se encuentra el programa, el escaneo
queda en `error` y no se ejecutan los pasos siguientes (sí la limpieza).

Java: primero `javaHome` de la configuración; si no, autodetectar en
`~/.sonar/cache/*/*_extracted/*/Contents/Home` (macOS) o
`~/.sonar/cache/*/*_extracted/*` (Windows), tomando la versión más nueva y
validando que exista `bin/java` (`bin\java.exe` en Windows); si no, `JAVA_HOME`.
El escáner JS: `scannerBin` de la configuración, luego
`~/tools/sonar-scanner-*/bin` (el más nuevo) o el PATH.

`check_tools` informa qué falta (token, Java, `dotnet`,
`dotnet-sonarscanner`, `sonar-scanner`, workspace) con un texto de ayuda;
la interfaz lo muestra para que el usuario sepa por qué no puede escanear.

## API de SonarQube

Autenticación: Basic con el token como usuario y contraseña vacía.
- `GET /api/system/status` → en línea o no.
- `POST /api/projects/create` (`project`, `name`) → crear. Si ya existe, tratarlo como éxito.
- `GET /api/qualitygates/project_status?projectKey=` → chip Aprobado / No aprobado. 404 = "Sin análisis".
- `GET /api/components/show?component=` → `analysisDate` para "Último escaneo". 404 = "Sin análisis".
  La fecha de la API manda; la fecha guardada localmente tras cada escaneo
  solo se usa si SonarQube no responde.
- 401 = token inválido: mostrarlo como aviso, nunca con el token en el texto.
- `GET /api/ce/component?component=` → saber cuándo terminó de procesarse un análisis.

## Diseño

Material Design 3, simple. Lee `docs/DISENO.md` antes de tocar la interfaz.
Las pantallas de referencia están en `docs/diseno/*.html` (abrirlas como
texto: el markup tiene los estilos exactos). CSS plano con variables en
`src/styles.css`, sin librerías de UI.

## Forma de trabajar

- Seguimos los hitos de `docs/PLAN.md`, uno a la vez. Al terminar cada
  hito (desde `src-tauri/` para cargo):
  - `cargo check`
  - `cargo check --target x86_64-pc-windows-msvc` (verifica que compile en
    Windows; requiere `rustup target add x86_64-pc-windows-msvc` una vez)
  - `npm run build`
  - resumen de lo hecho, y propón un commit.
- Después de cada hito que toque Rust, usa el subagente
  `revisor-multiplataforma`.
- Explica en español y en términos simples lo que haces en Rust.
