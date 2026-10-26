/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MIDAS_INTEGRATED_BRANCH: string;
  readonly VITE_MIDAS_INTEGRATED_COMMIT: string;
  readonly VITE_MIDAS_INTEGRATED_DIRTY: boolean;
}
