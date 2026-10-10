import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import { App } from './App';
import { AuthProvider } from './lib/auth';
import { I18nProvider } from './lib/i18n';
import { IS_NATIVE } from './lib/platform';
import './styles.css';

const container = document.getElementById('root');
if (!container) throw new Error('#root is missing from index.html');

createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <I18nProvider>
          <App />
        </I18nProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);

// The service worker is what makes the app installable and usable offline.
// Registration failures are not worth surfacing: the app works without it.
// The Android app skips it: its files are already on the device, and a
// worker caching them as well would only serve stale ones after an update.
if ('serviceWorker' in navigator && import.meta.env.PROD && !IS_NATIVE) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js').catch(() => undefined);
  });
}
