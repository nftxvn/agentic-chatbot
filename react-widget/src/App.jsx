import ChatWidget from './components/ChatWidget.jsx'

function App() {
  return (
    <div className="app">
      <div className="testing-banner">
        <span className="banner-icon">⚠️</span>
        <span>Mode Testing — Produksi menggunakan WhatsApp</span>
      </div>
      <ChatWidget />
    </div>
  )
}

export default App
