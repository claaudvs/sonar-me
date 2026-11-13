# Plan por hitos

Trabaja un hito a la vez. No avances sin que el anterior funcione.

## Hito 0: base ✅
- Proyecto creado con `npm create tauri-app@latest` (React + TypeScript). ✅
- En `tauri.conf.json`: `productName` y título de ventana "Sonar Local", 960×720.
- Agregar plugins: `npm run tauri add dialog store opener notification single-instance`.
- Agregar crates en `src-tauri/Cargo.toml`: `tokio` (features `process`,
  `io-util`, `sync`, `macros`, `rt`), `reqwest` (features `json`,
  `rustls-tls`, sin default features), `command-group` (feature `with-tokio`),
  `fix-path-env`.
- `fix_path_env::fix()` al iniciar en macOS.
- Quitar el demo de la plantilla (`greet`, `App.css`) y crear `src/styles.css`
  con los tokens de `docs/DISENO.md` y `src/lib/tauri.ts` vacío.
- `npm run tauri dev` abre la ventana.

## Hito 1: lista con datos de prueba
- Pantalla de lista igual a `docs/diseno/01-lista.html`, con datos fijos en React.
- Componentes: `ProjectList`, `ProjectRow`, `GateChip`, `ScanButton`.
- Incluir los estados de fila: normal, en cola, escaneando (paso y barra), error.
- Sin Rust todavía, solo interfaz.

## Hito 2: registro de proyectos y configuración
- Configuración `{ workspace, sonarUrl, tokenFile, javaHome?, scannerBin? }`
  en el plugin `store`, con valores por defecto (`sonarUrl` =
  `http://localhost:9000`, `tokenFile` = `~/.sonar/token`, workspace vacío).
  Comandos `get_settings`, `save_settings`.
- Struct `Project { id, name, key, path, kind (Dotnet|Js), solution?, sources?, layer }`
  guardado con el plugin `store`.
- Comandos `list_projects`, `inspect_folder` (detecta tipo, `.sln`/`.slnx`,
  `sources`, nombre, clave), `add_project`, `remove_project`.
- Flujo "Agregar" con el diálogo de `docs/diseno/02` y `03`, carpeta elegida
  con el plugin `dialog`. Al terminar, snackbar como en `04`.
- `suggest_projects`: subcarpetas del workspace con `.sln`, `.slnx`,
  `.csproj` o `package.json` que aún no están agregadas (vacío si no hay workspace).

## Hito 3: escanear .NET
- `check_tools`: qué herramientas faltan, mostrado en la interfaz.
- Cola en Rust, un escaneo a la vez, sin duplicados. Comandos `scan_project`, `cancel_scan`.
- Eventos `scan://status` y `scan://log` con los tipos definidos en CLAUDE.md.
- La fila muestra "Escaneando", el paso y la barra de progreso.
- Panel de log por proyecto (comando `scan_log` + evento `scan://log`),
  con el estilo de los diálogos de `docs/DISENO.md`.
- Cancelar mata el árbol de procesos y borra `.sonarqube`.
- Guardar fecha y resultado del último escaneo (respaldo si Sonar no responde).

## Hito 4: escanear JS/TS
- Mismo flujo con `sonar-scanner`, token por variable de entorno `SONAR_TOKEN`.
  Un solo paso visible: "Analizando".

## Hito 5: SonarQube
- Indicador "SonarQube en línea" en la cabecera.
- Crear el proyecto en Sonar al agregarlo (si se marcó la opción).
- Chip del quality gate y fecha del último análisis desde la API.
- Tras un escaneo, esperar a `api/ce` y refrescar la fila.
- Aviso claro si el token es inválido (401).

## Hito 6: pulido y entrega
- Notificación al terminar un escaneo con la app en segundo plano.
- "Escanear todos".
- Pantalla de configuración (editar lo creado en el Hito 2).
- Íconos y `npm run tauri build` (dmg en macOS, msi en Windows).
