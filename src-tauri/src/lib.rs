mod paths;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Una app abierta desde Finder no hereda el PATH de la terminal.
    // Debe ser lo primero: modifica variables de entorno, así que nada
    // que cree hilos (logger, runtime de tokio) puede ir antes.
    paths::fix_path();

    tauri::Builder::default()
        // Si se abre una segunda instancia, enfocamos la ventana existente.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error al iniciar la aplicación");
}
