/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MIDAS_SOURCE_REVISION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
