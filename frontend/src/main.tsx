import React from 'react';
import ReactDOM from 'react-dom/client';
import { BuilderApp } from './modules/builder/BuilderApp';
import { RuntimeApp } from './modules/runtime/RuntimeApp';
import './styles.css';

function AppRouter() {
  const path = window.location.pathname;
  if (path.startsWith('/builder')) {
    return <BuilderApp />;
  }
  return <RuntimeApp />;
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <AppRouter />
  </React.StrictMode>,
);
