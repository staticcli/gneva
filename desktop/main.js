const {
  app,
  BrowserWindow,
  Tray,
  Menu,
  ipcMain,
  Notification,
  protocol,
} = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");
const fs = require("fs");

const API_PORT = 8100;
const API_URL = `http://localhost:${API_PORT}`;
const DEV_FRONTEND_URL = "http://localhost:3000";
const HEALTH_ENDPOINT = `${API_URL}/health`;

let mainWindow = null;
let tray = null;
let apiProcess = null;
let isQuitting = false;

// ── Deep link protocol registration ──────────────────────────────────────────
if (process.defaultApp) {
  if (process.argv.length >= 2) {
    app.setAsDefaultProtocolClient("gneva", process.execPath, [
      path.resolve(process.argv[1]),
    ]);
  }
} else {
  app.setAsDefaultProtocolClient("gneva");
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function checkHealth() {
  return new Promise((resolve) => {
    const req = http.get(HEALTH_ENDPOINT, (res) => {
      resolve(res.statusCode >= 200 && res.statusCode < 400);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

function waitForApi(timeoutMs = 30000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const poll = async () => {
      if (Date.now() - start > timeoutMs) {
        return reject(new Error("API server did not start in time"));
      }
      const healthy = await checkHealth();
      if (healthy) return resolve();
      setTimeout(poll, 500);
    };
    poll();
  });
}

function spawnApiServer() {
  const pythonCmd = process.platform === "win32" ? "python" : "python3";
  apiProcess = spawn(
    pythonCmd,
    ["-m", "uvicorn", "gneva.main:app", "--port", String(API_PORT)],
    {
      cwd: path.resolve(__dirname, ".."),
      stdio: "pipe",
      shell: process.platform === "win32",
    }
  );

  apiProcess.stdout.on("data", (data) => {
    console.log(`[api] ${data.toString().trim()}`);
  });
  apiProcess.stderr.on("data", (data) => {
    console.error(`[api] ${data.toString().trim()}`);
  });
  apiProcess.on("close", (code) => {
    console.log(`[api] process exited with code ${code}`);
    apiProcess = null;
  });
}

function killApiServer() {
  if (!apiProcess) return;
  try {
    if (process.platform === "win32") {
      spawn("taskkill", ["/pid", String(apiProcess.pid), "/f", "/t"], {
        shell: true,
      });
    } else {
      apiProcess.kill("SIGTERM");
    }
  } catch (err) {
    console.error("Failed to kill API server:", err.message);
  }
  apiProcess = null;
}

function getFrontendUrl() {
  // In development, use the dev server if available
  if (!app.isPackaged) {
    return DEV_FRONTEND_URL;
  }
  // In production, serve built frontend from resources
  const builtPath = path.join(process.resourcesPath, "frontend", "index.html");
  if (fs.existsSync(builtPath)) {
    return `file://${builtPath}`;
  }
  return DEV_FRONTEND_URL;
}

// ── Window creation ──────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: "Gneva",
    titleBarStyle: "hiddenInset",
    titleBarOverlay:
      process.platform === "win32"
        ? { color: "#0f172a", symbolColor: "#94a3b8", height: 36 }
        : undefined,
    backgroundColor: "#0f172a",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Show loading screen first
  mainWindow.loadFile(path.join(__dirname, "index.html"));
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  // Minimise to tray on close
  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      return false;
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ── Tray ─────────────────────────────────────────────────────────────────────

function createTray() {
  // Use a simple placeholder — replace icons/tray.png with a real icon later
  const iconPath = path.join(__dirname, "icons", "tray.png");
  const fallbackIcon = path.join(__dirname, "icons", "icon.png");
  const icon = fs.existsSync(iconPath)
    ? iconPath
    : fs.existsSync(fallbackIcon)
    ? fallbackIcon
    : undefined;

  // Tray requires an icon; skip if none available yet (dev mode)
  if (!icon) {
    console.log("[tray] No icon found, skipping tray creation");
    return;
  }

  tray = new Tray(icon);
  tray.setToolTip("Gneva");

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Open Gneva",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on("double-click", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ── IPC handlers ─────────────────────────────────────────────────────────────

function setupIpc() {
  ipcMain.handle("notify", (_event, { title, body }) => {
    if (Notification.isSupported()) {
      new Notification({ title, body }).show();
    }
  });

  ipcMain.handle("get-version", () => app.getVersion());
  ipcMain.handle("get-platform", () => process.platform);
}

// ── Deep link handling ───────────────────────────────────────────────────────

function handleDeepLink(url) {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
    mainWindow.webContents.send("deep-link", url);
  }
}

// macOS: open-url event
app.on("open-url", (event, url) => {
  event.preventDefault();
  handleDeepLink(url);
});

// Windows/Linux: second-instance carries the deep link URL
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", (_event, argv) => {
    const deepLink = argv.find((arg) => arg.startsWith("gneva://"));
    if (deepLink) handleDeepLink(deepLink);
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ── App lifecycle ────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  setupIpc();
  createWindow();
  createTray();

  // Check if API is already running; if not, start it
  const alreadyRunning = await checkHealth();
  if (!alreadyRunning) {
    console.log("[app] API not running, spawning server...");
    spawnApiServer();
  } else {
    console.log("[app] API already running");
  }

  // Wait for API, then load the frontend
  try {
    await waitForApi();
    console.log("[app] API is ready, loading frontend");
    const frontendUrl = getFrontendUrl();
    mainWindow.loadURL(frontendUrl);
  } catch (err) {
    console.error("[app] Failed to start:", err.message);
    // Stay on loading screen — it will keep polling
  }

  // macOS: re-create window when dock icon clicked
  app.on("activate", () => {
    if (mainWindow === null) {
      createWindow();
    } else {
      mainWindow.show();
    }
  });
});

app.on("before-quit", () => {
  isQuitting = true;
});

app.on("will-quit", () => {
  killApiServer();
});

// On macOS, keep app running when all windows closed
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    isQuitting = true;
    app.quit();
  }
});
