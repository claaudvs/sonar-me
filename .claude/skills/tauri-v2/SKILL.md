---
name: tauri-v2
description: Referencia de Tauri v2 para Sonar Local. Úsala siempre que toques src-tauri/, tauri.conf.json, capabilities o plugins de Tauri.
---

# Tauri v2 en este proyecto

Internet está lleno de ejemplos de Tauri v1 que NO compilan en v2. Si un
ejemplo usa `tauri::api::*`, `allowlist` o `window.__TAURI__.tauri`, es v1: descártalo.

## Estructura
- Rust en `src-tauri/src/lib.rs` (punto de entrada `run()`), `main.rs` solo lo llama.
- Módulos sugeridos: `projects.rs` (registro), `scanner.rs` (cola y procesos),
  `sonar.rs` (API REST), `paths.rs` (detección de Java, escáneres, PATH).

## Rust ↔ React
- Comandos: `#[tauri::command]` async que devuelven `Result<T, String>`;
  registrarlos en `tauri::generate_handler![...]`.
- React: `invoke` de `@tauri-apps/api/core` y `listen` de `@tauri-apps/api/event`.
- Emitir eventos: `app.emit("scan://log", payload)` (trait `Emitter`).
- Estado compartido: `app.manage(...)` con `tokio::sync::Mutex`; acceder con `State<'_, T>`.
- Al montar, React pide el estado actual con un comando; no esperes solo a los eventos.

## Plugins y permisos
- Añadirlos con `npm run tauri add <nombre>`: configura Cargo, npm y permisos.
- "not allowed" en el frontend = falta el permiso en `src-tauri/capabilities/default.json`.
- `dialog`: `open({ directory: true })` desde React o `app.dialog().file().pick_folder()` en Rust.

## Procesos
- `tokio::process::Command` con `stdout(Stdio::piped())`, `stderr` también,
  leer con `BufReader::lines()` y emitir cada línea.
- Grupo de procesos con `command-group` para poder cancelar todo el árbol.
- Windows: añade `creation_flags(0x08000000)` (CREATE_NO_WINDOW) para que no
  aparezcan ventanas de consola.

## Plataforma
- `#[cfg(target_os = "windows")]` / `#[cfg(target_os = "macos")]`; todo debe compilar en ambos.
- macOS: `fix_path_env::fix()` al iniciar.
