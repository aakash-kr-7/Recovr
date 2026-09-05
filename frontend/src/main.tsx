import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ThemeProvider } from "./context/ThemeContext";
import { MerchantProvider } from "./context/MerchantContext";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <MerchantProvider>
          <App />
        </MerchantProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
