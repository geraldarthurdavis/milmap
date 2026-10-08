/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DATA_BASE_URL?: string;
  readonly VITE_PMTILES_URL?: string;
  readonly VITE_LABEL_COLLISION?: "0" | "1";
  readonly VITE_BASEMAP_FLAVOR?: "dark" | "light" | "grayscale" | "black" | "white";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
