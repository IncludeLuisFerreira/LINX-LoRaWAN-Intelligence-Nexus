import { useState } from 'react'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 space-y-12">
      {/* Indicador visual do Tailwind */}
      <div className="rounded-full bg-blue-500/10 px-4 py-1 border border-blue-500/30 text-blue-400 text-sm font-medium animate-pulse">
        ⚡ Tailwind CSS Ativo e Funcionando!
      </div>

      {/* Hero Section */}
      <section className="flex flex-col items-center text-center max-w-lg space-y-6">
        <div className="relative flex items-center justify-center">
          <img src={heroImg} className="w-36 h-auto opacity-80" alt="Hero background" />
          <img src={reactLogo} className="w-12 h-12 absolute -left-6 animate-spin-slow" alt="React logo" />
          <img src={viteLogo} className="w-12 h-12 absolute -right-6" alt="Vite logo" />
        </div>

        <div>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            Get started
          </h1>
          <p className="mt-2 text-slate-400">
            Edit <code className="bg-slate-800 px-2 py-1 rounded text-purple-300 font-mono text-sm">src/App.tsx</code> and save to test <code className="bg-slate-800 px-2 py-1 rounded text-purple-300 font-mono text-sm">HMR</code>
          </p>
        </div>

        <button
          type="button"
          className="rounded-lg bg-indigo-600 px-6 py-3 font-semibold text-white shadow-lg transition hover:bg-indigo-500 active:scale-95 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          onClick={() => setCount((count) => count + 1)}
        >
          Count is {count}
        </button>
      </section>

      {/* Dividir seções */}
      <div className="w-full max-w-2xl h-px bg-slate-800" />

      {/* Next Steps / Links */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full max-w-2xl">
        {/* Documentação */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 flex flex-col justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-200">Documentation</h2>
            <p className="text-sm text-slate-400 mt-1 mb-4">Your questions, answered</p>
          </div>
          <ul className="space-y-2">
            <li>
              <a
                href="https://vite.dev/"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 text-sm text-slate-300 hover:text-blue-400 transition"
              >
                <img src={viteLogo} className="w-4 h-4" alt="" />
                Explore Vite
              </a>
            </li>
            <li>
              <a
                href="https://react.dev/"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 text-sm text-slate-300 hover:text-blue-400 transition"
              >
                <img src={reactLogo} className="w-4 h-4" alt="" />
                Learn more
              </a>
            </li>
          </ul>
        </div>

        {/* Redes Sociais */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 flex flex-col justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-200">Connect with us</h2>
            <p className="text-sm text-slate-400 mt-1 mb-4">Join the Vite community</p>
          </div>
          <ul className="grid grid-cols-2 gap-2 text-sm">
            <li>
              <a href="https://github.com/vitejs/vite" target="_blank" rel="noreferrer" className="text-slate-300 hover:text-purple-400 transition">
                GitHub
              </a>
            </li>
            <li>
              <a href="https://chat.vite.dev/" target="_blank" rel="noreferrer" className="text-slate-300 hover:text-purple-400 transition">
                Discord
              </a>
            </li>
            <li>
              <a href="https://x.com/vite_js" target="_blank" rel="noreferrer" className="text-slate-300 hover:text-purple-400 transition">
                X.com
              </a>
            </li>
            <li>
              <a href="https://bsky.app/profile/vite.dev" target="_blank" rel="noreferrer" className="text-slate-300 hover:text-purple-400 transition">
                Bluesky
              </a>
            </li>
          </ul>
        </div>
      </section>
    </div>
  )
}

export default App