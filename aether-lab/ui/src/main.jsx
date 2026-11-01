import React, { Suspense, lazy, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "@fontsource-variable/space-grotesk";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/plus-jakarta-sans";
import "./index.css";

// Two pages, one build: the public site (#/) and the design lab (#/lab). Each loads only its own code.
const Site = lazy(() => import("./site/Site"));
const App = lazy(() => import("./App"));

const isLab = () => location.hash.startsWith("#/lab");

function Root() {
  const [lab, setLab] = useState(isLab());
  useEffect(() => {
    const on = () => setLab(isLab());
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  useEffect(() => { document.documentElement.classList.toggle("site-mode", !lab); }, [lab]);
  return <Suspense fallback={<div className="h-full w-full bg-ink-950" />}>{lab ? <App /> : <Site />}</Suspense>;
}

createRoot(document.getElementById("root")).render(<Root />);
