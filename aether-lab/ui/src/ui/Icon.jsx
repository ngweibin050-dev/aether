const P = {
  move: "M12 3v18M3 12h18M12 3l-3 3M12 3l3 3M12 21l-3-3M12 21l3-3M3 12l3-3M3 12l3 3M21 12l-3-3M21 12l-3 3",
  rotate: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
  scale: "M4 20h7v-7M4 20 20 4M13 4h7v7",
  undo: "M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3",
  redo: "m15 14 5-5-5-5M20 9H9a5 5 0 0 0 0 10h3",
  laptop: "M4 6h16v10H4zM2 19h20",
  hand: "M8 13V5.5a1.5 1.5 0 0 1 3 0V12M11 11V4a1.5 1.5 0 0 1 3 0v7M14 11V5.5a1.5 1.5 0 0 1 3 0V14a7 7 0 0 1-7 7h-.5A6.5 6.5 0 0 1 4 16l-1.5-3.2a1.4 1.4 0 0 1 2.4-1.4L8 15",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  eyeoff: "M3 3l18 18M10.6 6.1A10 10 0 0 1 12 6c6 0 10 6 10 6a17 17 0 0 1-3.2 3.9M6.6 6.6C3.9 8.4 2 12 2 12s4 6 10 6a9.7 9.7 0 0 0 4.4-1",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13",
  plus: "M12 5v14M5 12h14",
  wave: "M2 12c2-4 4-4 6 0s4 4 6 0 4-4 6 0",
  layers: "m12 3 9 5-9 5-9-5 9-5zM3 13l9 5 9-5",
  panel: "M4 4h16v16H4zM9 4v16",
  send: "M4 12l16-8-6 16-2-7-8-1z",
  mic: "M9 3h6v12H9zM5 11a7 7 0 0 0 14 0M12 18v3",
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  cube: "m12 2 9 5v10l-9 5-9-5V7zM3 7l9 5 9-5M12 12v10",
  chevron: "m9 6 6 6-6 6",
  close: "M6 6l12 12M18 6 6 18",
  target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  upload: "M12 15V3M7 8l5-5 5 5M4 17v3h16v-3",
};
export default function Icon({ name, className = "w-4 h-4" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round"><path d={P[name]} /></svg>
  );
}
