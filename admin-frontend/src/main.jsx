import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { initFormValidationLocalization } from './utils/formValidation'

// Inisialisasi lokalisasi pesan validasi form HTML5 ke Bahasa Indonesia
initFormValidationLocalization()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
