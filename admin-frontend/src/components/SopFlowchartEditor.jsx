/**
 * SopFlowchartEditor.jsx
 *
 * Komponen editor flowchart SOP interaktif berbasis @xyflow/react.
 * Memungkinkan admin memuat data tabel Markdown dari AI, lalu menyusun
 * ulang alur flowchart secara visual (drag & drop, tambah edge, ubah shape).
 *
 * Fitur:
 *  - Parse tabel Markdown → node awal (tanpa edge)
 *  - Swimlane per pelaksana (kolom horizontal)
 *  - Node shape: rectangle (proses) & diamond (keputusan)
 *  - Edge berlabel "Benar" / "Salah" / kosong
 *  - Auto-save draft (debounce 2 detik)
 *  - Tombol Finalize → konversi JSON → Markdown → re-embed
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  BackgroundVariant,
  MiniMap,
  Handle,
  Position,
  MarkerType,
  Panel,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { flowchartApi } from '../api/flowchart'

/* ─────────────────────────────────────────────
   Utilitas: Parse tabel Markdown → array rows
   ───────────────────────────────────────────── */
function parseMarkdownTable(markdown) {
  if (!markdown) return []
  const lines = markdown.split('\n').filter(l => l.trim())
  // Cari baris yang dimulai dengan | dan mengandung data (bukan separator)
  const tableLines = lines.filter(l => l.trim().startsWith('|') && !l.match(/^\|[-| ]+\|$/))
  if (tableLines.length < 2) return []

  // Baris pertama = header
  const headers = tableLines[0]
    .split('|')
    .map(h => h.trim())
    .filter(Boolean)

  const rows = []
  for (let i = 1; i < tableLines.length; i++) {
    const cells = tableLines[i]
      .split('|')
      .map(c => c.trim())
      .filter(Boolean)
    if (cells.length === 0) continue
    const row = {}
    headers.forEach((h, idx) => {
      row[h] = cells[idx] || ''
    })
    rows.push(row)
  }
  return rows
}

/* ─────────────────────────────────────────────
   Utilitas: Normalisasi nama kolom header
   ───────────────────────────────────────────── */
function normalizeRow(row) {
  // Cari key yang cocok case-insensitive
  const find = (keys) => {
    for (const k of Object.keys(row)) {
      if (keys.some(key => k.toLowerCase().includes(key.toLowerCase()))) {
        return row[k]
      }
    }
    return ''
  }
  return {
    stepNo: parseInt(find(['No', 'no'])) || 0,
    label: find(['Uraian', 'uraian', 'Prosedur', 'prosedur']),
    pelaksana: find(['Pelaksana', 'pelaksana']),
    waktu: find(['Waktu', 'waktu']),
    output: find(['Output', 'output']),
    kelengkapan: find(['Kelengkapan', 'kelengkapan']),
    keterangan: find(['Ket', 'ket', 'Keterangan']),
  }
}

/* ─────────────────────────────────────────────
   Utilitas: Heuristic deteksi diamond (keputusan)
   ───────────────────────────────────────────── */
function detectShape(label) {
  if (!label) return 'rectangle'
  const lower = label.toLowerCase()
  if (
    lower.includes('jika') ||
    lower.includes('apabila') ||
    lower.includes('bila') ||
    lower.includes('benar') ||
    lower.includes('salah') ||
    lower.includes('verifikasi') ||
    lower.includes('evaluasi') ||
    lower.includes('cek') ||
    lower.includes('periksa')
  ) {
    return 'diamond'
  }
  return 'rectangle'
}

/* ─────────────────────────────────────────────
   Custom Node: SOP Node (rectangle / diamond)
   ───────────────────────────────────────────── */
function SopNode({ data, selected }) {
  const isDiamond = data.shape === 'diamond'
  const isStart = data.shape === 'oval-start'
  const isEnd = data.shape === 'oval-end'

  const pelaksanaColor = PELAKSANA_COLORS[data.pelaksana] || '#64748b'

  if (isStart || isEnd) {
    return (
      <div
        style={{
          background: isStart
            ? 'linear-gradient(135deg, #0ea5e9, #0284c7)'
            : 'linear-gradient(135deg, #10b981, #059669)',
          border: selected ? '2px solid #f59e0b' : '2px solid transparent',
          borderRadius: '50px',
          padding: '8px 20px',
          minWidth: 100,
          textAlign: 'center',
          color: '#fff',
          fontWeight: 700,
          fontSize: 12,
          boxShadow: selected ? '0 0 0 3px rgba(245,158,11,0.3)' : '0 2px 8px rgba(0,0,0,0.2)',
          cursor: 'default',
          userSelect: 'none',
        }}
      >
        <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
        {data.label}
        <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      </div>
    )
  }

  if (isDiamond) {
    return (
      <div style={{ position: 'relative', width: 140, height: 80 }}>
        <Handle type="target" position={Position.Top} style={{ top: -6, left: '50%', transform: 'translateX(-50%)' }} />
        <svg
          width={140}
          height={80}
          style={{ position: 'absolute', top: 0, left: 0, overflow: 'visible' }}
        >
          <polygon
            points="70,4 136,40 70,76 4,40"
            fill={selected ? '#fef3c7' : '#fff7ed'}
            stroke={selected ? '#f59e0b' : '#f97316'}
            strokeWidth={selected ? 2.5 : 1.5}
          />
        </svg>
        <div
          style={{
            position: 'absolute',
            top: 0, left: 0, width: 140, height: 80,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 20px',
            pointerEvents: 'none',
          }}
        >
          <span style={{
            fontSize: 9,
            fontWeight: 700,
            color: pelaksanaColor,
            textTransform: 'uppercase',
            letterSpacing: 0.5,
            marginBottom: 2,
          }}>
            {data.stepNo ? `#${data.stepNo}` : ''}
          </span>
          <span style={{
            fontSize: 9,
            color: '#92400e',
            textAlign: 'center',
            lineHeight: 1.3,
            maxWidth: 100,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
          }}>
            {data.label}
          </span>
        </div>
        <Handle type="source" position={Position.Bottom} style={{ bottom: -6, left: '50%', transform: 'translateX(-50%)' }} id="bottom" />
        <Handle type="source" position={Position.Right} style={{ right: -6, top: '50%', transform: 'translateY(-50%)' }} id="right" />
        <Handle type="source" position={Position.Left} style={{ left: -6, top: '50%', transform: 'translateY(-50%)' }} id="left" />
      </div>
    )
  }

  // Rectangle (default)
  return (
    <div
      style={{
        background: selected ? '#f0f9ff' : '#ffffff',
        border: selected ? '2px solid #0ea5e9' : `2px solid ${pelaksanaColor}30`,
        borderLeft: `4px solid ${pelaksanaColor}`,
        borderRadius: 8,
        padding: '8px 12px',
        minWidth: 160,
        maxWidth: 200,
        boxShadow: selected
          ? `0 0 0 3px ${pelaksanaColor}20, 0 4px 16px rgba(0,0,0,0.1)`
          : '0 2px 8px rgba(0,0,0,0.08)',
        cursor: 'default',
        userSelect: 'none',
        transition: 'all 0.15s',
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
        {data.stepNo ? (
          <span style={{
            background: pelaksanaColor,
            color: '#fff',
            borderRadius: '50%',
            width: 18,
            height: 18,
            fontSize: 10,
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            {data.stepNo}
          </span>
        ) : null}
        <span style={{
          fontSize: 9,
          fontWeight: 700,
          color: pelaksanaColor,
          textTransform: 'uppercase',
          letterSpacing: 0.5,
        }}>
          {data.pelaksana ? data.pelaksana.split(' ').slice(0, 2).join(' ') : ''}
        </span>
      </div>
      <div style={{
        fontSize: 10,
        color: '#1e293b',
        lineHeight: 1.4,
        overflow: 'hidden',
        display: '-webkit-box',
        WebkitLineClamp: 4,
        WebkitBoxOrient: 'vertical',
      }}>
        {data.label}
      </div>
      {(data.waktu || data.output) && (
        <div style={{
          marginTop: 6,
          paddingTop: 5,
          borderTop: '1px solid #e2e8f0',
          display: 'flex',
          gap: 6,
          flexWrap: 'wrap',
        }}>
          {data.waktu && (
            <span style={{ fontSize: 8.5, color: '#64748b', background: '#f1f5f9', borderRadius: 4, padding: '1px 5px' }}>
              ⏱ {data.waktu}
            </span>
          )}
          {data.output && (
            <span style={{ fontSize: 8.5, color: '#0369a1', background: '#e0f2fe', borderRadius: 4, padding: '1px 5px', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              📄 {data.output}
            </span>
          )}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

/* ─────────────────────────────────────────────
   Palet warna per pelaksana (auto-assign)
   ───────────────────────────────────────────── */
const PALETTE = [
  '#0284c7', '#7c3aed', '#059669', '#dc2626',
  '#d97706', '#db2777', '#0891b2', '#65a30d',
]
const PELAKSANA_COLORS = {}

function assignPelaksanaColor(pelaksana) {
  if (!PELAKSANA_COLORS[pelaksana]) {
    const idx = Object.keys(PELAKSANA_COLORS).length % PALETTE.length
    PELAKSANA_COLORS[pelaksana] = PALETTE[idx]
  }
  return PELAKSANA_COLORS[pelaksana]
}

/* ─────────────────────────────────────────────
   Konversi rows Markdown → ReactFlow nodes
   ───────────────────────────────────────────── */
function rowsToNodes(rows) {
  // Reset color map agar konsisten
  Object.keys(PELAKSANA_COLORS).forEach(k => delete PELAKSANA_COLORS[k])

  // Kumpulkan pelaksana unik
  const pelaksanaList = [...new Set(rows.map(r => r.pelaksana).filter(Boolean))]
  pelaksanaList.forEach(p => assignPelaksanaColor(p))

  const LANE_WIDTH = 240
  const NODE_HEIGHT = 110
  const V_GAP = 40
  const H_PAD = 20

  // Hitung x per pelaksana
  const pelaksanaX = {}
  pelaksanaList.forEach((p, i) => {
    pelaksanaX[p] = H_PAD + i * LANE_WIDTH
  })

  const nodes = []

  rows.forEach((row, idx) => {
    const shape = detectShape(row.label)
    const x = pelaksanaX[row.pelaksana] ?? H_PAD
    const y = idx * (NODE_HEIGHT + V_GAP) + 60

    nodes.push({
      id: `node-${row.stepNo || idx + 1}`,
      type: 'sopNode',
      position: { x, y },
      data: {
        stepNo: row.stepNo,
        label: row.label,
        pelaksana: row.pelaksana,
        waktu: row.waktu,
        output: row.output,
        kelengkapan: row.kelengkapan,
        keterangan: row.keterangan,
        shape,
      },
    })
  })

  return { nodes, pelaksanaList }
}

/* ─────────────────────────────────────────────
   Node types registry
   ───────────────────────────────────────────── */
const nodeTypes = { sopNode: SopNode }

/* ─────────────────────────────────────────────
   Default edge style
   ───────────────────────────────────────────── */
const defaultEdgeOptions = {
  type: 'smoothstep',
  markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#64748b' },
  style: { stroke: '#94a3b8', strokeWidth: 1.5 },
  labelStyle: { fontSize: 10, fontWeight: 600 },
  labelBgStyle: { fill: '#fff', fillOpacity: 0.9 },
  labelBgPadding: [4, 3],
  labelBgBorderRadius: 4,
}

/* ─────────────────────────────────────────────
   Panel: Swimlane Headers
   ───────────────────────────────────────────── */
function SwimlaneHeader({ pelaksanaList }) {
  const LANE_WIDTH = 240
  const H_PAD = 20
  return (
    <div style={{
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      height: 50,
      display: 'flex',
      pointerEvents: 'none',
      zIndex: 4,
    }}>
      {pelaksanaList.map((p, i) => (
        <div
          key={p}
          style={{
            width: LANE_WIDTH,
            marginLeft: i === 0 ? H_PAD : 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: `${PELAKSANA_COLORS[p]}15`,
            borderBottom: `2px solid ${PELAKSANA_COLORS[p]}40`,
            borderRight: i < pelaksanaList.length - 1 ? `1px dashed ${PELAKSANA_COLORS[p]}30` : 'none',
          }}
        >
          <span style={{
            fontSize: 10,
            fontWeight: 700,
            color: PELAKSANA_COLORS[p],
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}>
            {p}
          </span>
        </div>
      ))}
    </div>
  )
}

/* ─────────────────────────────────────────────
   Sidebar: Info panel untuk node terpilih
   ───────────────────────────────────────────── */
function NodeSidebar({ node, onClose, onUpdate }) {
  const [form, setForm] = useState({ ...node.data })

  const handleChange = (field, val) => {
    setForm(f => ({ ...f, [field]: val }))
  }

  const handleSave = () => {
    onUpdate(node.id, form)
    onClose()
  }

  return (
    <div style={{
      position: 'fixed',
      right: 0,
      top: 0,
      bottom: 0,
      width: 300,
      background: 'var(--bg-card)',
      borderLeft: '1px solid var(--border-color)',
      padding: 20,
      overflowY: 'auto',
      zIndex: 100,
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      boxShadow: '-4px 0 20px rgba(0,0,0,0.1)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>
          Edit Node #{form.stepNo}
        </span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--text-muted)' }}>✕</button>
      </div>

      {[
        { label: 'Uraian Prosedur', field: 'label', type: 'textarea' },
        { label: 'Pelaksana', field: 'pelaksana', type: 'text' },
        { label: 'Waktu', field: 'waktu', type: 'text' },
        { label: 'Output', field: 'output', type: 'text' },
        { label: 'Kelengkapan', field: 'kelengkapan', type: 'textarea' },
        { label: 'Keterangan', field: 'keterangan', type: 'text' },
      ].map(({ label, field, type }) => (
        <div key={field}>
          <label style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
            {label}
          </label>
          {type === 'textarea' ? (
            <textarea
              value={form[field] || ''}
              onChange={e => handleChange(field, e.target.value)}
              style={{ width: '100%', minHeight: 70, fontSize: 12, resize: 'vertical' }}
              className="w-full"
            />
          ) : (
            <input
              type="text"
              value={form[field] || ''}
              onChange={e => handleChange(field, e.target.value)}
              style={{ width: '100%', fontSize: 12 }}
              className="w-full"
            />
          )}
        </div>
      ))}

      <div>
        <label style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
          Shape
        </label>
        <select
          value={form.shape || 'rectangle'}
          onChange={e => handleChange('shape', e.target.value)}
          className="w-full"
          style={{ fontSize: 12 }}
        >
          <option value="rectangle">⬛ Proses (Persegi)</option>
          <option value="diamond">🔷 Keputusan (Belah Ketupat)</option>
          <option value="oval-start">🟢 Mulai (Oval)</option>
          <option value="oval-end">🔴 Selesai (Oval)</option>
        </select>
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button
          onClick={handleSave}
          style={{
            flex: 1,
            background: 'var(--brand-primary)',
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            padding: '8px 0',
            fontSize: 12,
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          Simpan Perubahan
        </button>
        <button
          onClick={onClose}
          style={{
            flex: 1,
            background: 'var(--bg-input)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: 8,
            padding: '8px 0',
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          Batal
        </button>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────
   Dialog: Tambah edge label
   ───────────────────────────────────────────── */
function EdgeLabelDialog({ open, onConfirm, onCancel }) {
  const [label, setLabel] = useState('')
  if (!open) return null
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
    }}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 16, padding: 24,
        width: 320, boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        <p style={{ fontWeight: 700, marginBottom: 12, color: 'var(--text-primary)' }}>Label Koneksi (opsional)</p>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
          Contoh: "Benar", "Salah", atau kosongkan untuk tanpa label
        </p>
        <input
          autoFocus
          type="text"
          value={label}
          onChange={e => setLabel(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') onConfirm(label); if (e.key === 'Escape') onCancel() }}
          placeholder="Benar / Salah / kosong"
          className="w-full"
          style={{ marginBottom: 16 }}
        />
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => onConfirm(label)}
            style={{ flex: 1, background: 'var(--brand-primary)', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 0', fontWeight: 700, cursor: 'pointer', fontSize: 13 }}
          >
            Tambah Koneksi
          </button>
          <button
            onClick={onCancel}
            style={{ flex: 1, background: 'var(--bg-input)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)', borderRadius: 8, padding: '8px 0', cursor: 'pointer', fontSize: 13 }}
          >
            Batal
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────
   Komponen Utama: SopFlowchartEditor
   ───────────────────────────────────────────── */
export default function SopFlowchartEditor({ documentId, markdownContent, category }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [pelaksanaList, setPelaksanaList] = useState([])

  const [selectedNode, setSelectedNode] = useState(null)
  const [pendingConnection, setPendingConnection] = useState(null)
  const [showEdgeDialog, setShowEdgeDialog] = useState(false)

  const [saveState, setSaveState] = useState('idle') // idle | saving | saved | error
  const [finalizeState, setFinalizeState] = useState('idle') // idle | loading | success | error
  const [finalizeMsg, setFinalizeMsg] = useState('')
  const [flowchartStatus, setFlowchartStatus] = useState('draft')
  const [initialized, setInitialized] = useState(false)

  const saveTimeout = useRef(null)

  /* ── Load flowchart dari backend atau parse markdown ── */
  useEffect(() => {
    async function init() {
      try {
        const res = await flowchartApi.get(documentId)
        if (res.nodes?.length > 0) {
          // Sudah ada data di backend
          const loadedNodes = res.nodes
          // Re-assign pelaksana colors
          const pelList = [...new Set(loadedNodes.map(n => n.data?.pelaksana).filter(Boolean))]
          pelList.forEach(p => assignPelaksanaColor(p))
          setPelaksanaList(pelList)
          setNodes(loadedNodes)
          setEdges(res.edges || [])
          setFlowchartStatus(res.flowchart_status || 'draft')
          setInitialized(true)
          return
        }
      } catch (e) {
        // Belum ada, parse dari markdown
      }

      // Parse dari markdown
      if (markdownContent) {
        importFromMarkdown(markdownContent)
      }
      setInitialized(true)
    }
    init()
  }, [documentId])

  /* ── Import dari markdown tabel ── */
  const importFromMarkdown = useCallback((md) => {
    // Ambil section "Teks Bersih" atau ambil semua tabel yang ada
    let target = md
    if (md.includes('## 2.')) {
      target = md.split('## 2.')[1]
    } else if (md.includes('Teks Bersih')) {
      target = md.split('Teks Bersih')[1]
    }

    const rawRows = parseMarkdownTable(target)
    const rows = rawRows.map(normalizeRow).filter(r => r.stepNo > 0 || r.label)

    if (rows.length === 0) return

    const { nodes: newNodes, pelaksanaList: pList } = rowsToNodes(rows)
    setPelaksanaList(pList)
    setNodes(newNodes)
    setEdges([])
  }, [])

  /* ── Auto-save dengan debounce ── */
  const triggerAutoSave = useCallback((newNodes, newEdges) => {
    if (!initialized) return
    if (saveTimeout.current) clearTimeout(saveTimeout.current)
    setSaveState('saving')
    saveTimeout.current = setTimeout(async () => {
      try {
        await flowchartApi.save(documentId, newNodes, newEdges)
        setSaveState('saved')
        setTimeout(() => setSaveState('idle'), 2000)
      } catch {
        setSaveState('error')
      }
    }, 2000)
  }, [documentId, initialized])

  const handleNodesChange = useCallback((changes) => {
    onNodesChange(changes)
  }, [onNodesChange])

  const handleEdgesChange = useCallback((changes) => {
    onEdgesChange(changes)
  }, [onEdgesChange])

  /* ── Saat user selesai drag node ── */
  const handleNodeDragStop = useCallback((_, __, currentNodes) => {
    triggerAutoSave(currentNodes, edges)
  }, [edges, triggerAutoSave])

  /* ── Saat user menghubungkan dua node ── */
  const onConnect = useCallback((params) => {
    setPendingConnection(params)
    setShowEdgeDialog(true)
  }, [])

  const handleEdgeLabelConfirm = useCallback((label) => {
    setShowEdgeDialog(false)
    if (!pendingConnection) return

    const edgeColor = label === 'Benar' ? '#10b981'
      : label === 'Salah' ? '#ef4444'
      : '#94a3b8'

    const newEdge = {
      ...pendingConnection,
      id: `edge-${Date.now()}`,
      label: label || undefined,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: edgeColor },
      style: { stroke: edgeColor, strokeWidth: 1.8 },
      labelStyle: { fontSize: 10, fontWeight: 700, fill: edgeColor },
      labelBgStyle: { fill: '#fff', fillOpacity: 0.95 },
      labelBgPadding: [4, 3],
      labelBgBorderRadius: 4,
    }

    setEdges(eds => {
      const updated = addEdge(newEdge, eds)
      triggerAutoSave(nodes, updated)
      return updated
    })
    setPendingConnection(null)
  }, [pendingConnection, nodes, triggerAutoSave])

  const handleEdgeLabelCancel = useCallback(() => {
    setShowEdgeDialog(false)
    setPendingConnection(null)
  }, [])

  /* ── Klik node → buka sidebar edit ── */
  const onNodeClick = useCallback((_, node) => {
    setSelectedNode(node)
  }, [])

  /* ── Update node data dari sidebar ── */
  const handleNodeUpdate = useCallback((nodeId, newData) => {
    setNodes(nds => {
      const updated = nds.map(n => n.id === nodeId ? { ...n, data: { ...n.data, ...newData } } : n)
      triggerAutoSave(updated, edges)
      return updated
    })
  }, [edges, triggerAutoSave])

  /* ── Tambah node baru ── */
  const addNode = useCallback((shape = 'rectangle') => {
    const id = `node-new-${Date.now()}`
    const newNode = {
      id,
      type: 'sopNode',
      position: { x: 200 + Math.random() * 100, y: 200 + Math.random() * 100 },
      data: {
        stepNo: nodes.length + 1,
        label: shape === 'oval-start' ? 'Mulai' : shape === 'oval-end' ? 'Selesai' : 'Langkah Baru',
        pelaksana: pelaksanaList[0] || '',
        waktu: '',
        output: '',
        kelengkapan: '',
        keterangan: '',
        shape,
      },
    }
    setNodes(nds => {
      const updated = [...nds, newNode]
      triggerAutoSave(updated, edges)
      return updated
    })
  }, [nodes, pelaksanaList, edges, triggerAutoSave])

  /* ── Finalize → convert → re-embed ── */
  const handleFinalize = async () => {
    if (nodes.length === 0) return
    setFinalizeState('loading')
    setFinalizeMsg('')
    try {
      // Simpan dulu
      await flowchartApi.save(documentId, nodes, edges)
      // Lalu finalize
      const res = await flowchartApi.finalize(documentId)
      setFinalizeState('success')
      setFinalizeMsg(res.message || 'Flowchart berhasil difinalisasi dan di-embed ke RAG.')
      setFlowchartStatus('finalized')
    } catch (err) {
      setFinalizeState('error')
      setFinalizeMsg(err.response?.data?.message || 'Gagal finalisasi. Coba lagi.')
    }
  }

  /* ── Reset import dari markdown ── */
  const handleReImport = () => {
    if (!markdownContent) return
    if (!window.confirm('Ini akan menghapus semua node dan edge yang ada. Lanjutkan?')) return
    importFromMarkdown(markdownContent)
  }

  /* ─────────────────────────────
     Render
     ───────────────────────────── */
  return (
    <div style={{ position: 'relative', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* ── Toolbar ── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 16px',
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border-color)',
        flexWrap: 'wrap',
      }}>
        {/* Status badge */}
        <span style={{
          fontSize: 11,
          fontWeight: 700,
          padding: '3px 10px',
          borderRadius: 20,
          background: flowchartStatus === 'finalized' ? '#d1fae5' : '#fef3c7',
          color: flowchartStatus === 'finalized' ? '#065f46' : '#92400e',
          border: `1px solid ${flowchartStatus === 'finalized' ? '#a7f3d0' : '#fde68a'}`,
        }}>
          {flowchartStatus === 'finalized' ? '✅ Finalized' : '✏️ Draft'}
        </span>

        {/* Save state */}
        {saveState !== 'idle' && (
          <span style={{ fontSize: 11, color: saveState === 'error' ? '#ef4444' : '#64748b' }}>
            {saveState === 'saving' ? '⏳ Menyimpan...' : saveState === 'saved' ? '✓ Tersimpan' : '⚠️ Gagal simpan'}
          </span>
        )}

        <div style={{ flex: 1 }} />

        {/* Add node buttons */}
        <button
          onClick={() => addNode('rectangle')}
          title="Tambah node proses"
          style={toolbarBtnStyle('#1e293b')}
        >
          + Proses
        </button>
        <button
          onClick={() => addNode('diamond')}
          title="Tambah node keputusan"
          style={toolbarBtnStyle('#d97706')}
        >
          + Keputusan
        </button>
        <button
          onClick={() => addNode('oval-start')}
          title="Tambah node mulai"
          style={toolbarBtnStyle('#0284c7')}
        >
          + Mulai
        </button>
        <button
          onClick={() => addNode('oval-end')}
          title="Tambah node selesai"
          style={toolbarBtnStyle('#059669')}
        >
          + Selesai
        </button>

        {/* Re-import */}
        {markdownContent && (
          <button
            onClick={handleReImport}
            title="Import ulang dari hasil AI"
            style={{ ...toolbarBtnStyle('#7c3aed'), fontSize: 11 }}
          >
            ↺ Import AI
          </button>
        )}

        {/* Finalize button */}
        <button
          onClick={handleFinalize}
          disabled={finalizeState === 'loading' || nodes.length === 0}
          style={{
            background: finalizeState === 'success'
              ? 'linear-gradient(135deg, #10b981, #059669)'
              : 'linear-gradient(135deg, #0284c7, #0369a1)',
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            padding: '7px 16px',
            fontSize: 12,
            fontWeight: 700,
            cursor: nodes.length === 0 || finalizeState === 'loading' ? 'not-allowed' : 'pointer',
            opacity: nodes.length === 0 ? 0.5 : 1,
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            transition: 'all 0.2s',
          }}
        >
          {finalizeState === 'loading' ? '⏳ Memproses...'
            : finalizeState === 'success' ? '✅ Finalized!'
            : '🚀 Finalize & Embed'}
        </button>
      </div>

      {/* Finalize message */}
      {finalizeMsg && (
        <div style={{
          padding: '8px 16px',
          background: finalizeState === 'success' ? '#d1fae5' : '#fee2e2',
          color: finalizeState === 'success' ? '#065f46' : '#991b1b',
          fontSize: 12,
          fontWeight: 600,
          borderBottom: '1px solid var(--border-color)',
        }}>
          {finalizeMsg}
        </div>
      )}

      {/* Empty state */}
      {nodes.length === 0 && initialized && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 12,
          pointerEvents: 'none',
          zIndex: 5,
          marginTop: 52,
        }}>
          <div style={{ fontSize: 48, lineHeight: 1 }}>🗂️</div>
          <p style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>Canvas kosong</p>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', maxWidth: 280 }}>
            {markdownContent
              ? 'Klik "↺ Import AI" untuk mengimpor otomatis dari hasil ekstraksi AI, atau tambah node secara manual.'
              : 'Tambah node secara manual menggunakan tombol di toolbar atas.'}
          </p>
        </div>
      )}

      {/* ── Canvas ReactFlow ── */}
      <div style={{ flex: 1, position: 'relative' }}>
        {pelaksanaList.length > 0 && <SwimlaneHeader pelaksanaList={pelaksanaList} />}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onNodeDragStop={handleNodeDragStop}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.2}
          maxZoom={2}
          style={{ background: 'var(--bg-main)' }}
          deleteKeyCode={['Backspace', 'Delete']}
          proOptions={{ hideAttribution: true }}
        >
          <Controls style={{ bottom: 20, left: 20 }} />
          <MiniMap
            nodeColor={n => PELAKSANA_COLORS[n.data?.pelaksana] || '#94a3b8'}
            style={{ bottom: 20, right: 20, borderRadius: 8, border: '1px solid var(--border-color)' }}
          />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border-color)" />

          <Panel position="top-right" style={{ margin: 10 }}>
            <div style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: 8,
              padding: '8px 12px',
              fontSize: 10,
              color: 'var(--text-muted)',
              lineHeight: 1.8,
            }}>
              <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: 4 }}>Tips</strong>
              🖱️ Drag node untuk pindah<br />
              🔗 Drag dari ◉ ke node lain untuk koneksi<br />
              🖱️ Klik node untuk edit detail<br />
              ⌫ Pilih + Delete untuk hapus
            </div>
          </Panel>
        </ReactFlow>
      </div>

      {/* ── Sidebar edit node ── */}
      {selectedNode && (
        <NodeSidebar
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          onUpdate={handleNodeUpdate}
        />
      )}

      {/* ── Dialog label edge ── */}
      <EdgeLabelDialog
        open={showEdgeDialog}
        onConfirm={handleEdgeLabelConfirm}
        onCancel={handleEdgeLabelCancel}
      />
    </div>
  )
}

/* ─────────────────────────────────────────────
   Helper: style tombol toolbar
   ───────────────────────────────────────────── */
function toolbarBtnStyle(color) {
  return {
    background: `${color}15`,
    color: color,
    border: `1px solid ${color}30`,
    borderRadius: 8,
    padding: '6px 12px',
    fontSize: 11,
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.15s',
    whiteSpace: 'nowrap',
  }
}

/* ─────────────────────────────────────────────
   Wrapper dengan ReactFlowProvider
   ───────────────────────────────────────────── */
export function SopFlowchartEditorWrapper(props) {
  return (
    <ReactFlowProvider>
      <SopFlowchartEditor {...props} />
    </ReactFlowProvider>
  )
}
