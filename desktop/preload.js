const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("gneva", {
  /** Current OS: "win32" | "darwin" | "linux" */
  platform: process.platform,

  /**
   * Show a native OS notification.
   * @param {string} title
   * @param {string} body
   */
  notify: (title, body) => ipcRenderer.invoke("notify", { title, body }),

  /**
   * Register a callback for gneva:// deep link navigation.
   * @param {(url: string) => void} callback
   */
  onDeepLink: (callback) => {
    ipcRenderer.on("deep-link", (_event, url) => callback(url));
  },

  /**
   * Get the app version from package.json.
   * @returns {Promise<string>}
   */
  getVersion: () => ipcRenderer.invoke("get-version"),
});
