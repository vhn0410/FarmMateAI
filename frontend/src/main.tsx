import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider, theme } from 'reablocks'
import './index.css'
import 'reachat/index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <App />
    </ThemeProvider>
  </StrictMode>,
)
