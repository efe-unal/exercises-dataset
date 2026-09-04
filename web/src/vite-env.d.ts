/// <reference types="vite/client" />

/** Build-time configuration the app reads from the environment. */
interface ImportMetaEnv {
  /** Where the API lives in production; unset means same-origin. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
