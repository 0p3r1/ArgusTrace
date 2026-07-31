import { Link, Route, Routes } from 'react-router-dom'
import './App.css'
import { BrandMark } from './icons.jsx'
import InvestigatePage from './InvestigatePage.jsx'
import ToolInfoPage from './ToolInfoPage.jsx'

function App() {
  return (
    <div className="page">
      <header className="site-header">
        <Link to="/" className="brand">
          <BrandMark />
          <h1>ArgusTrace</h1>
        </Link>
        <p className="tagline">Modular OSINT investigation, one entity at a time.</p>
      </header>

      <Routes>
        <Route path="/" element={<InvestigatePage />} />
        <Route path="/tools/:family" element={<ToolInfoPage />} />
      </Routes>
    </div>
  )
}

export default App
