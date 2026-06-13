import React from 'react';
import ReactDOM from 'react-dom/client';
import { RuntimeApp } from './modules/runtime/RuntimeApp';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <RuntimeApp />
  </React.StrictMode>,
);
