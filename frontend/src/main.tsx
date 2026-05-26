import React from "react";
import ReactDOM from "react-dom/client";
import { Toaster } from "sonner";
import { App } from "./App";
import { ThemeProvider } from "./theme";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <Toaster richColors closeButton position="bottom-right" />
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
