#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::env;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread::sleep;
use std::time::Duration;
use tauri::State;

struct DesktopState {
    backend_child: Mutex<Option<Child>>,
    backend_status: Mutex<BackendStatus>,
}

#[derive(Clone, Default, Serialize)]
struct BackendStatus {
    running: bool,
    url: String,
    ws_url: String,
    mode: String,
    message: Option<String>,
}

impl DesktopState {
    fn new() -> Self {
        Self {
            backend_child: Mutex::new(None),
            backend_status: Mutex::new(BackendStatus::default()),
        }
    }
}

#[tauri::command]
fn desktop_backend_status(state: State<'_, DesktopState>) -> BackendStatus {
    state.backend_status.lock().expect("backend status lock poisoned").clone()
}

fn main() {
    let desktop_state = DesktopState::new();
    let initial_status = spawn_backend(&desktop_state);

    {
        let mut status = desktop_state
            .backend_status
            .lock()
            .expect("backend status lock poisoned");
        *status = initial_status;
    }

    let app = tauri::Builder::default()
        .manage(desktop_state)
        .invoke_handler(tauri::generate_handler![desktop_backend_status])
        .build(tauri::generate_context!())
        .expect("error while building SuperAjan12 desktop app");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            let state: State<'_, DesktopState> = app_handle.state();
            if let Some(mut child) = state
                .backend_child
                .lock()
                .expect("backend child lock poisoned")
                .take()
            {
                let _ = child.kill();
            }
        }
    });
}

fn spawn_backend(state: &DesktopState) -> BackendStatus {
    let host = env::var("SUPERAJAN12_BACKEND_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port = env::var("SUPERAJAN12_BACKEND_PORT").unwrap_or_else(|_| "8000".to_string());
    let url = format!("http://{}:{}", host, port);
    let ws_url = format!("ws://{}:{}", host, port);
    let startup_timeout_ms = env::var("SUPERAJAN12_BACKEND_STARTUP_TIMEOUT_MS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(8000);

    if env::var("SUPERAJAN12_BACKEND_DISABLE_AUTOSTART")
        .map(|value| value == "1" || value.eq_ignore_ascii_case("true"))
        .unwrap_or(false)
    {
        return BackendStatus {
            running: false,
            url,
            ws_url,
            mode: "external".to_string(),
            message: Some("desktop sidecar autostart disabled; expecting external backend".to_string()),
        };
    }

    let repo_root = env::var("SUPERAJAN12_REPO_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../.."));
    let python_path = env::var("SUPERAJAN12_BACKEND_PYTHON").unwrap_or_else(|_| "python3".to_string());
    let module_path = repo_root.join("src");

    let mut pythonpath_value = module_path.display().to_string();
    if let Some(existing) = env::var_os("PYTHONPATH") {
        let separator = if cfg!(windows) { ";" } else { ":" };
        pythonpath_value = format!("{}{}{}", pythonpath_value, separator, existing.to_string_lossy());
    }

    let mut command = Command::new(python_path);
    command
        .arg("-m")
        .arg("superajan12.backend_server")
        .arg("--host")
        .arg(&host)
        .arg("--port")
        .arg(&port)
        .current_dir(&repo_root)
        .env("PYTHONPATH", pythonpath_value)
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    match command.spawn() {
        Ok(mut child) => {
            if wait_for_backend_ready(&host, &port, startup_timeout_ms) {
                *state
                    .backend_child
                    .lock()
                    .expect("backend child lock poisoned") = Some(child);
                BackendStatus {
                    running: true,
                    url,
                    ws_url,
                    mode: "sidecar".to_string(),
                    message: Some("desktop sidecar backend started and passed health check".to_string()),
                }
            } else {
                let _ = child.kill();
                let _ = child.wait();
                BackendStatus {
                    running: false,
                    url,
                    ws_url,
                    mode: "external".to_string(),
                    message: Some(format!(
                        "desktop sidecar failed health check within {} ms; expecting external backend",
                        startup_timeout_ms
                    )),
                }
            }
        }
        Err(error) => BackendStatus {
            running: false,
            url,
            ws_url,
            mode: "external".to_string(),
            message: Some(format!("desktop sidecar start failed: {}", error)),
        },
    }
}

fn wait_for_backend_ready(host: &str, port: &str, timeout_ms: u64) -> bool {
    let address = format!("{}:{}", host, port);
    let attempts = (timeout_ms / 200).max(1);
    for _ in 0..attempts {
        if backend_healthcheck(&address) {
            return true;
        }
        sleep(Duration::from_millis(200));
    }
    false
}

fn backend_healthcheck(address: &str) -> bool {
    let mut stream = match TcpStream::connect(address) {
        Ok(stream) => stream,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));

    if stream
        .write_all(b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        .is_err()
    {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }

    response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200")
}
