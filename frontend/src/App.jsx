import { useState, useEffect, useCallback } from "react"

const API = ""

// แนบรหัสผ่าน (ถ้าเจ้าของตั้งไว้) ให้ทุกคำขออัตโนมัติ
const _realFetch = window.fetch.bind(window)
let _appPassword = localStorage.getItem("top10_pw") || ""
let _prompting = false

function askPassword(force = false) {
  if (_prompting && !force) return _appPassword
  if (_prompting) return _appPassword
  _prompting = true
  try {
    const pw = window.prompt(
      force
        ? "รหัสผ่านไม่ถูกต้อง — ใส่รหัสผ่านแอป Top10 Bot อีกครั้ง:"
        : "ใส่รหัสผ่านแอป Top10 Bot เพื่อใช้งาน:"
    )
    if (pw) {
      _appPassword = pw
      localStorage.setItem("top10_pw", pw)
    }
  } finally {
    _prompting = false
  }
  return _appPassword
}

window.fetch = async (input, init = {}) => {
  const send = () => {
    const headers = new Headers(init.headers || {})
    if (_appPassword) headers.set("X-App-Password", _appPassword)
    return _realFetch(input, { ...init, headers })
  }
  let res = await send()
  if (res.status === 401 && !String(input).includes("/health")) {
    askPassword(true)
    if (_appPassword) res = await send()
  }
  return res
}

const STATUS_LABEL = {
  queued: "รอคิว",
  processing: "กำลังทำงาน",
  completed: "เสร็จแล้ว",
  failed: "ล้มเหลว",
}

const STATUS_COLOR = {
  queued: "text-gray-500 bg-gray-100",
  processing: "text-amber-700 bg-amber-100",
  completed: "text-green-700 bg-green-100",
  failed: "text-red-700 bg-red-100",
}

function Badge({ status }) {
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
        STATUS_COLOR[status] || "bg-gray-100 text-gray-600"
      }`}
    >
      {STATUS_LABEL[status] || status}
    </span>
  )
}

function Settings({ config, onSaved }) {
  const [open, setOpen] = useState(false)
  const [provider, setProvider] = useState(config?.provider || "gemini")
  const [model, setModel] = useState(config?.gemini_model || "gemini-2.5-flash")
  const [keyInput, setKeyInput] = useState("")
  const [ollamaModel, setOllamaModel] = useState(config?.ollama_model || "llama3.1:8b")
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState("")

  useEffect(() => {
    if (config) {
      setProvider(config.provider)
      setModel(config.gemini_model)
      setOllamaModel(config.ollama_model)
    }
  }, [config])

  const save = async () => {
    setSaving(true)
    setMsg("")
    try {
      const body = { provider, gemini_model: model, ollama_model: ollamaModel }
      if (keyInput.trim()) body.gemini_api_key = keyInput.trim()
      const res = await fetch(`${API}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setKeyInput("")
      setMsg("บันทึกแล้ว ✅")
      onSaved?.(data)
    } catch (e) {
      setMsg("บันทึกไม่สำเร็จ: " + (e.message || ""))
    } finally {
      setSaving(false)
    }
  }

  const missingKey = provider === "gemini" && !config?.gemini_key_set

  return (
    <section className="bg-white p-6 rounded-2xl shadow-sm ring-1 ring-slate-200 mb-6">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between text-left"
      >
        <h2 className="text-lg font-semibold text-slate-900">
          ⚙️ ตั้งค่า AI
          <span className="ml-2 text-xs font-normal text-slate-500">
            {config
              ? `${config.provider === "gemini" ? "Gemini" : "Ollama"} · ${
                  config.provider === "gemini" ? config.gemini_model : config.ollama_model
                }`
              : "กำลังโหลด..."}
          </span>
        </h2>
        <span className="text-slate-400">{open ? "▲" : "▼"}</span>
      </button>

      {missingKey && !open && (
        <p className="mt-3 text-sm text-amber-700 bg-amber-50 p-3 rounded-lg">
          ⚠️ ยังไม่ได้ใส่ Gemini API key — กดเพื่อเปิดตั้งค่า แล้ววางคีย์
        </p>
      )}

      {open && (
        <div className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              ผู้สร้างสคริป
            </label>
            <div className="flex gap-2">
              {[
                ["gemini", "Gemini (คุณภาพดีสุด)"],
                ["ollama", "Ollama (ในเครื่อง ฟรี)"],
              ].map(([val, label]) => (
                <button
                  key={val}
                  onClick={() => setProvider(val)}
                  className={`px-3 py-1.5 rounded-lg text-sm border transition ${
                    provider === val
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-slate-600 border-slate-300 hover:border-blue-400"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {provider === "gemini" ? (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Gemini API key
                  {config?.gemini_key_set && (
                    <span className="ml-2 text-xs text-green-700">
                      ตั้งไว้แล้ว ({config.gemini_key_hint})
                    </span>
                  )}
                </label>
                <input
                  type="password"
                  className="w-full border border-slate-300 rounded-lg p-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={
                    config?.gemini_key_set
                      ? "เว้นว่างไว้ถ้าไม่ต้องการเปลี่ยน"
                      : "วางคีย์ที่ได้จาก aistudio.google.com/apikey"
                  }
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                />
                <p className="text-xs text-slate-500 mt-1">
                  ขอฟรีได้ที่{" "}
                  <a
                    href="https://aistudio.google.com/apikey"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    aistudio.google.com/apikey
                  </a>{" "}
                  — เก็บไว้ในเครื่องพี่เท่านั้น ไม่ส่งไปที่อื่น
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  โมเดล
                </label>
                <input
                  list="gemini-models"
                  className="w-full border border-slate-300 rounded-lg p-2.5"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
                <datalist id="gemini-models">
                  <option value="gemini-3.6-flash">gemini-3.6-flash — ใหม่ ล่าสุด แนะนำ</option>
                  <option value="gemini-3-flash-preview">gemini-3-flash-preview — เร็ว ลื่น</option>
                  <option value="gemini-3.5-flash">gemini-3.5-flash</option>
                  <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite — เร็ว/โควตาประหยัด</option>
                  <option value="gemini-3.1-pro-preview">gemini-3.1-pro-preview — คุณภาพสูง (โควตาจำกัด)</option>
                </datalist>
                <p className="text-xs text-slate-500 mt-1">
                  พิมพ์ชื่อโมเดลเองได้ · ถ้าโมเดลนี้ใช้ไม่ได้ ระบบจะสลับตัวสำรองให้อัตโนมัติ
                </p>
              </div>
            </>
          ) : (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                ชื่อโมเดล Ollama
              </label>
              <input
                className="w-full border border-slate-300 rounded-lg p-2.5"
                value={ollamaModel}
                onChange={(e) => setOllamaModel(e.target.value)}
              />
              <p className="text-xs text-slate-500 mt-1">
                ต้อง pull โมเดลไว้ก่อน (เช่น scb10x/typhoon2.5-qwen3-30b-a3b)
              </p>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={save}
              disabled={saving}
              className="bg-slate-800 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-slate-900 disabled:opacity-50"
            >
              {saving ? "กำลังบันทึก..." : "บันทึกการตั้งค่า"}
            </button>
            {msg && <span className="text-sm text-slate-600">{msg}</span>}
          </div>
        </div>
      )}
    </section>
  )
}

export default function App() {
  const [topic, setTopic] = useState("")
  const [minutes, setMinutes] = useState(5)
  const [loading, setLoading] = useState(false)
  const [current, setCurrent] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState("")
  const [config, setConfig] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)

  const loadConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API}/config`)
      if (res.ok) setConfig(await res.json())
    } catch {
      /* ignore */
    }
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API}/jobs`)
      if (res.ok) setHistory(await res.json())
    } catch {
      /* backend ยังไม่ขึ้น */
    }
  }, [])

  // เช็คว่าเซิร์ฟเวอร์บังคับใส่รหัสผ่านไหม → ถามครั้งเดียวก่อนโหลดข้อมูล
  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const res = await _realFetch(`${API}/health`)
        const h = await res.json()
        if (alive && h.auth_required && !_appPassword) askPassword(false)
      } catch {
        /* backend ยังไม่ตื่น — ปล่อยไป */
      }
      if (alive) setAuthChecked(true)
    })()
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    if (!authChecked) return
    loadHistory()
    loadConfig()
  }, [authChecked, loadHistory, loadConfig])

  // poll งานที่กำลังทำ + รีเฟรชประวัติ
  useEffect(() => {
    if (!current) return
    if (current.status === "completed" || current.status === "failed") return
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/jobs/${current.job_id}`)
        if (res.ok) setCurrent(await res.json())
        loadHistory()
      } catch {
        /* keep polling */
      }
    }, 3000)
    return () => clearTimeout(t)
  }, [current, loadHistory])

  const createJob = async () => {
    if (!topic.trim()) return
    setLoading(true)
    setError("")
    try {
      const res = await fetch(`${API}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ topic: topic.trim(), minutes: Number(minutes) }),
      })
      if (!res.ok) {
        const txt = await res.text()
        throw new Error(txt)
      }
      const data = await res.json()
      setCurrent({ ...data, topic: topic.trim(), minutes: Number(minutes) })
      loadHistory()
    } catch (e) {
      setError(
        "เชื่อมต่อ backend ไม่ได้ หรือข้อมูลไม่ถูกต้อง: " + (e.message || "")
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6 md:p-10">
      <div className="max-w-3xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900">
            🎬 Top10 Bot
          </h1>
          <p className="text-slate-600 mt-1">
            สร้างสคริป + สตอรี่บอร์ด 10 อันดับ พร้อมรูปภาพ — ทำงานเบื้องหลังไม่จำกัดเวลา
          </p>
        </header>

        <Settings config={config} onSaved={setConfig} />

        <section className="bg-white p-6 rounded-2xl shadow-sm ring-1 ring-slate-200 mb-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">สร้างงานใหม่</h2>

          <label className="block text-sm font-medium text-slate-700 mb-1">
            หัวข้อ
          </label>
          <input
            className="w-full border border-slate-300 rounded-lg p-2.5 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="เช่น 10 อันดับสถานที่ท่องเที่ยวญี่ปุ่น"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createJob()}
          />

          <label className="block text-sm font-medium text-slate-700 mb-1">
            ความยาววิดีโอ (นาที)
          </label>
          <div className="flex items-center gap-3 mb-5">
            <input
              type="number"
              min="1"
              max="120"
              className="w-28 border border-slate-300 rounded-lg p-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={minutes}
              onChange={(e) => setMinutes(e.target.value)}
            />
            <div className="flex gap-2">
              {[3, 5, 8, 10, 15].map((m) => (
                <button
                  key={m}
                  onClick={() => setMinutes(m)}
                  className={`px-3 py-1.5 rounded-lg text-sm border transition ${
                    Number(minutes) === m
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-slate-600 border-slate-300 hover:border-blue-400"
                  }`}
                >
                  {m} นาที
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={createJob}
            disabled={loading || !topic.trim()}
            className="w-full md:w-auto bg-blue-600 text-white px-8 py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "กำลังส่งงาน..." : "🚀 สร้างสคริป + ค้นหารูป"}
          </button>

          {config?.provider === "gemini" && !config.gemini_key_set && (
            <p className="text-sm text-amber-700 bg-amber-50 p-3 rounded-lg mt-3">
              ⚠️ ยังไม่ได้ใส่ Gemini API key — เปิด «ตั้งค่า AI» ด้านบนเพื่อวางคีย์ก่อนสร้างงาน
            </p>
          )}

          {error && <p className="text-red-600 text-sm mt-3">{error}</p>}
        </section>

        {current && (
          <section className="bg-white p-6 rounded-2xl shadow-sm ring-1 ring-slate-200 mb-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-slate-900">งานปัจจุบัน</h2>
              <Badge status={current.status} />
            </div>
            <p className="text-slate-700">
              <span className="font-medium">{current.topic}</span>
              <span className="text-slate-400"> · {current.minutes} นาที</span>
            </p>

            {current.status === "processing" && (
              <div className="mt-4">
                <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                  <div className="h-full w-1/3 bg-blue-500 animate-pulse" />
                </div>
                <p className="text-sm text-slate-500 mt-2">
                  กำลังเขียนสคริปและค้นหารูป... (1 นาที ≈ 1–3 นาทีประมวลผล)
                </p>
              </div>
            )}

            {current.drive_folder_link && (
              <div className="mt-4 p-3 bg-green-50 rounded-lg space-y-2">
                {(current.local_folder_path ||
                  current.drive_folder_link.startsWith("local:")) && (
                  <div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() =>
                          fetch(`${API}/jobs/${current.job_id}/open?file=script.docx`, {
                            method: "POST",
                          })
                        }
                        className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-700"
                      >
                        📄 เปิดไฟล์บทพูด (Word)
                      </button>
                      <button
                        onClick={() =>
                          fetch(
                            `${API}/jobs/${current.job_id}/open?file=storyboard.docx`,
                            { method: "POST" }
                          )
                        }
                        className="bg-purple-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-purple-700"
                      >
                        🎬 เปิดสตอรี่บอร์ด (Word)
                      </button>
                      <button
                        onClick={() =>
                          fetch(
                            `${API}/jobs/${current.job_id}/open?file=video_prompts.docx`,
                            { method: "POST" }
                          )
                        }
                        className="bg-amber-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-amber-700"
                      >
                        🎞 พรอมป์ตวิดีโอ 10 วิ (Word)
                      </button>
                      <button
                        onClick={() =>
                          fetch(`${API}/jobs/${current.job_id}/open`, {
                            method: "POST",
                          })
                        }
                        className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-green-700"
                      >
                        📁 เปิดโฟลเดอร์ผลลัพธ์
                      </button>
                    </div>
                    <p className="text-xs text-slate-500 break-all mt-2">
                      {current.local_folder_path ||
                        current.drive_folder_link.slice(6)}
                    </p>
                  </div>
                )}
                {current.drive_folder_link.startsWith("https://") && (
                  <a
                    href={current.drive_folder_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block text-blue-700 font-medium hover:underline"
                  >
                    📂 เปิดโฟลเดอร์ใน Google Drive
                  </a>
                )}
                {current.drive_folder_link.startsWith("local:") &&
                  current.status === "completed" && (
                    <button
                      onClick={async () => {
                        const res = await fetch(
                          `${API}/jobs/${current.job_id}/upload-drive`,
                          { method: "POST" }
                        )
                        const data = await res.json()
                        if (res.ok) {
                          const fresh = await fetch(
                            `${API}/jobs/${current.job_id}`
                          ).then((r) => r.json())
                          setCurrent(fresh)
                          loadHistory()
                          window.open(data.link, "_blank", "noopener,noreferrer")
                        } else {
                          alert(data.detail || "อัปโหลดไม่สำเร็จ")
                        }
                      }}
                      className="block bg-sky-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-sky-700"
                    >
                      ☁️ อัปโหลดงานนี้ขึ้น Google Drive
                    </button>
                  )}
              </div>
            )}

            {current.error && (
              <p className="text-sm text-amber-700 mt-3 bg-amber-50 p-3 rounded-lg">
                {current.error}
              </p>
            )}
          </section>
        )}

        <section className="bg-white p-6 rounded-2xl shadow-sm ring-1 ring-slate-200">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900">ประวัติงาน</h2>
            <button
              onClick={loadHistory}
              className="text-sm text-blue-600 hover:underline"
            >
              รีเฟรช
            </button>
          </div>

          {history.length === 0 && (
            <p className="text-sm text-slate-500">ยังไม่มีงาน</p>
          )}

          <ul className="divide-y divide-slate-100">
            {history.map((j) => (
              <li key={j.job_id} className="py-3 flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-medium text-slate-800 truncate">{j.topic}</p>
                  <p className="text-xs text-slate-500">
                    {j.minutes} นาที · {j.created_at?.slice(0, 19)}
                  </p>
                  {j.drive_folder_link && !j.drive_folder_link.startsWith("local:") && (
                    <a
                      href={j.drive_folder_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline"
                    >
                      เปิด Drive
                    </a>
                  )}
                  {j.drive_folder_link && j.drive_folder_link.startsWith("local:") && (
                    <button
                      onClick={() =>
                        fetch(`${API}/jobs/${j.job_id}/open`, { method: "POST" })
                      }
                      className="text-xs text-green-700 hover:underline"
                    >
                      เปิดโฟลเดอร์
                    </button>
                  )}
                </div>
                <Badge status={j.status} />
              </li>
            ))}
          </ul>
        </section>

        <footer className="text-center text-xs text-slate-400 mt-8">
          รันในเครื่องพี่เอง · Ollama + FastAPI + SQLite · ไม่มีค่าใช้จ่ายรายเดือน
        </footer>
      </div>
    </div>
  )
}
