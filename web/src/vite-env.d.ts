/// <reference types="vite/client" />

/** Build-time configuration the app reads from the environment. */
interface ImportMetaEnv {
  /** Where the API lives in production; unset means same-origin. */
  readonly VITE_API_URL?: string;
  /** `athlete` or `operator` for the two Android apps; unset is the web app. */
  readonly VITE_APP_MODE?: string;
  /** The public web app, which shared profile links point at. */
  readonly VITE_PUBLIC_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
