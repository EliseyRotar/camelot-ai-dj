#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::env;

struct SidecarHandle(Mutex<Option<Child>>);

fn main() {
    // Spawn the Python sidecar automatically when the Tauri app starts.
    let sidecar = SidecarHandle(Mutex::new(None));

    tauri::Builder::default()
        .manage(sidecar)
        .setup(|app| {
            // Resolve sidecar path: <project_root>/sidecar/main.py
            // In dev, current dir is the project root. We look for the venv python.
            let resource_path = app
                .path()
                .resolve("../sidecar", tauri::PathResolver::ResourceDir)
                .unwrap_or_else(|_| std::path::PathBuf::from("../sidecar"));

            // Try venv python first, fall back to system python
            let venv_python = resource_path.join(".venv").join("Scripts").join("python.exe");
            let (exe, py_file) = if venv_python.exists() {
                (venv_python.to_string_lossy().to_string(), resource_path.join("main.py"))
            } else {
                ("python".to_string(), resource_path.join("main.py"))
            };

            let py_file_str = py_file.to_string_lossy().to_string();

            println!("[camelot] Launching sidecar: {} {}", exe, py_file_str);

            let child = Command::new(&exe)
                .arg(&py_file_str)
                .current_dir(resource_path.clone())
                .stdin(Stdio::null())
                .stdout(Stdio::inherit())
                .stderr(Stdio::inherit())
                .spawn();

            match child {
                Ok(c) => {
                    let state: tauri::State<SidecarHandle> = app.state();
                    *state.0.lock().unwrap() = Some(c);
                }
                Err(e) => {
                    eprintln!("[camelot] Failed to launch sidecar: {}. The UI will show DISCONNECTED. Run `python sidecar/main.py` manually.", e);
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Kill the sidecar when the window closes
                let state: tauri::State<SidecarHandle> = window.app_handle().state();
                if let Some(mut child) = state.0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}