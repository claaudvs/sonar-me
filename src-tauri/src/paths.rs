//! Detección de rutas: PATH del sistema (y más adelante Java y escáneres).

/// En macOS, copia el PATH de la shell del usuario y agrega las carpetas
/// donde suelen estar `dotnet`, `dotnet-sonarscanner` y `sonar-scanner`.
/// En Windows y Linux no hace nada.
#[cfg(target_os = "macos")]
pub fn fix_path() {
    use std::path::PathBuf;

    let _ = fix_path_env::fix();

    let mut entries: Vec<PathBuf> = std::env::var_os("PATH")
        .map(|p| std::env::split_paths(&p).collect())
        .unwrap_or_default();

    let mut extra: Vec<PathBuf> = Vec::new();
    if let Some(home) = std::env::var_os("HOME") {
        extra.push(PathBuf::from(home).join(".dotnet").join("tools"));
    }
    extra.push(PathBuf::from("/usr/local/share/dotnet"));
    extra.push(PathBuf::from("/opt/homebrew/bin"));
    extra.push(PathBuf::from("/usr/local/bin"));

    for dir in extra {
        if !entries.contains(&dir) {
            entries.push(dir);
        }
    }

    if let Ok(joined) = std::env::join_paths(entries) {
        // SAFETY: se llama al inicio de `run()`, antes de crear hilos.
        unsafe { std::env::set_var("PATH", joined) };
    }
}

#[cfg(not(target_os = "macos"))]
pub fn fix_path() {}
