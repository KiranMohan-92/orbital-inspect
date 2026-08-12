import React from "react";
import ReactDOM from "react-dom/client";
import "../index.css";
import "./landing.css";
import Landing from "./Landing";

const root = document.getElementById("root");
if (!root) throw new Error("Root element #root not found");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <Landing />
  </React.StrictMode>
);
