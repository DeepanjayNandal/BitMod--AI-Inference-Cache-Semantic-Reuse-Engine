"use client"

import { useState, useEffect } from "react"

// The final wordmark lines — each line has a blue part and orange part
const BLUE = "hsl(217,91%,60%)"
const ORANGE = "hsl(24,94%,53%)"
const GREEN = "hsl(142,71%,45%)"
const DIM = "hsl(215,20%,35%)"
const WHITE = "hsl(0,0%,95%)"
const RED = "hsl(0,72%,51%)"
const CYAN = "hsl(187,85%,53%)"
const PURPLE = "hsl(270,70%,65%)"

const LINES_BLUE = [
  "██████╗  ██╗████████╗",
  "██╔══██╗ ██║╚══██╔══╝",
  "██████╔╝ ██║   ██║   ",
  "██╔══██╗ ██║   ██║   ",
  "██████╔╝ ██║   ██║   ",
  "╚═════╝  ╚═╝   ╚═╝   ",
]

const LINES_ORANGE = [
  "███╗   ███╗ ██████╗ ██████╗ ",
  "████╗ ████║██╔═══██╗██╔══██╗",
  "██╔████╔██║██║   ██║██║  ██║",
  "██║╚██╔╝██║██║   ██║██║  ██║",
  "██║ ╚═╝ ██║╚██████╔╝██████╔╝",
  "╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ",
]

const FULL_LINES = LINES_BLUE.map((b, i) => b + LINES_ORANGE[i])
const LINE_LEN = Math.max(...FULL_LINES.map(l => l.length))
const NUM_LINES = FULL_LINES.length
const BLUE_LEN = LINES_BLUE[0].length

const SCRAMBLE_CHARS = "█▓░╔╗╚╝║═╬╣╠╦╩▌▐▀▄■□●○◆◇"
const BINARY_CHARS = "01"

function randomChar(pool: string) {
  return pool[Math.floor(Math.random() * pool.length)]
}

function colorForIndex(col: number): string {
  return col < BLUE_LEN ? BLUE : ORANGE
}

function RenderGrid({ grid, colors, label, showLabel }: {
  grid: string[][]
  colors: string[][]
  label?: string
  showLabel?: boolean
}) {
  return (
    <div className="relative">
      {showLabel && label && (
        <div className="absolute -top-6 left-0 text-[10px] font-mono text-muted-foreground opacity-70">
          {label}
        </div>
      )}
      <pre className="inline-block text-left leading-[1.15]">
        {grid.map((row, r) => (
          <div key={r}>
            {row.map((ch, c) => (
              <span key={c} style={{ color: colors[r]?.[c] ?? DIM }}>{ch}</span>
            ))}
          </div>
        ))}
      </pre>
    </div>
  )
}

function makeGrid(fill?: string): string[][] {
  return FULL_LINES.map(line =>
    Array.from({ length: line.length }, (_, i) => fill ?? line[i])
  )
}

function makeColors(color?: string): string[][] {
  return FULL_LINES.map((line, r) =>
    Array.from({ length: line.length }, (_, c) => color ?? colorForIndex(c))
  )
}

function finalGrid(): string[][] {
  return FULL_LINES.map(line => Array.from(line))
}

function finalColors(): string[][] {
  return makeColors()
}

// Total characters to type through
const TOTAL_CHARS = FULL_LINES.reduce((sum, line) => sum + line.length, 0)

// ─── Animation 1: Cache Hit Cascade ───────────────────────────────
function useCacheHitCascade(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("> lookup --query bitmod")

  useEffect(() => {
    if (!active) return
    setGrid(makeGrid(" "))
    setColors(makeColors(DIM))
    setLabel("> lookup --query bitmod")

    const final = finalGrid()
    const fc = finalColors()
    let col = 0

    const timer = setInterval(() => {
      if (col >= LINE_LEN) {
        clearInterval(timer)
        setLabel("[CACHE HIT] served in 0.3ms")
        setColors(makeColors(WHITE))
        setTimeout(() => setColors(fc), 150)
        return
      }
      setGrid(prev => prev.map((row, r) => {
        const next = [...row]
        if (col < final[r].length) next[col] = final[r][col]
        return next
      }))
      setColors(prev => prev.map((row, r) => {
        const next = [...row]
        if (col < final[r].length) next[col] = fc[r][col]
        return next
      }))
      col++
    }, 25)

    return () => clearInterval(timer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 2: Matrix Rain Resolve ─────────────────────────────
function useMatrixRainResolve(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(GREEN))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    setLabel("// matrix decode")
    const final = finalGrid()
    const fc = finalColors()
    const locked = Array(LINE_LEN).fill(false)
    let lockCount = 0

    const rainTimer = setInterval(() => {
      setGrid(prev => prev.map((row, r) =>
        row.map((ch, c) => locked[c] ? final[r][c] : randomChar(SCRAMBLE_CHARS))
      ))
      setColors(prev => prev.map((row, r) =>
        row.map((_, c) => locked[c] ? fc[r][c] : GREEN)
      ))

      const tolock = Math.floor(Math.random() * 3) + 2
      for (let i = 0; i < tolock && lockCount < LINE_LEN; i++) {
        let idx = Math.floor(Math.random() * LINE_LEN)
        let tries = 0
        while (locked[idx] && tries < 20) { idx = Math.floor(Math.random() * LINE_LEN); tries++ }
        if (!locked[idx]) { locked[idx] = true; lockCount++ }
      }

      if (lockCount >= LINE_LEN) {
        clearInterval(rainTimer)
        setGrid(final)
        setColors(fc)
        setLabel("")
      }
    }, 50)

    return () => clearInterval(rainTimer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 3: Binary Decode ───────────────────────────────────
function useBinaryDecode(active: boolean) {
  const [grid, setGrid] = useState(makeGrid("0"))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    setLabel("// decoding binary stream")
    setGrid(makeGrid("0"))
    setColors(makeColors(DIM))
    const final = finalGrid()
    const fc = finalColors()
    let decoded = 0

    const timer = setInterval(() => {
      setGrid(prev => prev.map((row, r) =>
        row.map((ch, c) => c < decoded ? final[r][c] : randomChar(BINARY_CHARS))
      ))
      setColors(prev => prev.map((row, r) =>
        row.map((_, c) => c < decoded ? fc[r][c] : DIM)
      ))
      decoded += 1
      if (decoded > LINE_LEN) {
        clearInterval(timer)
        setGrid(final)
        setColors(fc)
        setLabel("")
      }
    }, 35)

    return () => clearInterval(timer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 4: Network Propagation ─────────────────────────────
function useNetworkPropagation(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    setLabel("// propagating cache entry")
    setGrid(makeGrid(" "))
    const final = finalGrid()
    const fc = finalColors()
    const centerX = Math.floor(LINE_LEN / 2)
    const centerY = Math.floor(NUM_LINES / 2)
    let radius = 0

    const timer = setInterval(() => {
      setGrid(prev => prev.map((row, r) =>
        row.map((ch, c) => {
          const dist = Math.sqrt((c - centerX) ** 2 + ((r - centerY) * 3) ** 2)
          return dist <= radius ? final[r][c] : (dist <= radius + 3 ? "·" : " ")
        })
      ))
      setColors(prev => prev.map((row, r) =>
        row.map((_, c) => {
          const dist = Math.sqrt((c - centerX) ** 2 + ((r - centerY) * 3) ** 2)
          return dist <= radius ? fc[r][c] : DIM
        })
      ))
      radius += 2
      if (radius > LINE_LEN) {
        clearInterval(timer)
        setGrid(final)
        setColors(fc)
        setLabel("")
      }
    }, 40)

    return () => clearInterval(timer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 5: Query → Answer Morph ────────────────────────────
function useQueryAnswerMorph(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    const queryText = "> what is bitmod?"
    const final = finalGrid()
    const fc = finalColors()

    setLabel("> query")
    const qGrid = makeGrid(" ")
    const midRow = Math.floor(NUM_LINES / 2)
    const startCol = Math.floor((LINE_LEN - queryText.length) / 2)
    for (let i = 0; i < queryText.length; i++) {
      if (startCol + i >= 0 && startCol + i < qGrid[midRow].length) {
        qGrid[midRow][startCol + i] = queryText[i]
      }
    }
    setGrid(qGrid)
    setColors(makeColors(DIM))

    const t1 = setTimeout(() => {
      setLabel("// resolving...")
      let ticks = 0
      const scrambleTimer = setInterval(() => {
        const progress = ticks / 20
        setGrid(prev => prev.map((row, r) =>
          row.map((ch, c) => {
            if (Math.random() < progress) return final[r][c]
            return randomChar(SCRAMBLE_CHARS)
          })
        ))
        setColors(prev => prev.map((row, r) =>
          row.map((_, c) => {
            if (Math.random() < progress) return fc[r][c]
            return DIM
          })
        ))
        ticks++
        if (ticks > 25) {
          clearInterval(scrambleTimer)
          setGrid(final)
          setColors(fc)
          setLabel("")
        }
      }, 60)
    }, 1000)

    return () => clearTimeout(t1)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 6: Defragment ──────────────────────────────────────
function useDefragment(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    setLabel("// defragmenting cache")
    const final = finalGrid()
    const fc = finalColors()

    type Particle = { ch: string; color: string; targetR: number; targetC: number; curR: number; curC: number }
    const particles: Particle[] = []
    for (let r = 0; r < NUM_LINES; r++) {
      for (let c = 0; c < final[r].length; c++) {
        if (final[r][c] !== " ") {
          particles.push({
            ch: final[r][c], color: fc[r][c],
            targetR: r, targetC: c,
            curR: Math.floor(Math.random() * NUM_LINES),
            curC: Math.floor(Math.random() * LINE_LEN),
          })
        }
      }
    }

    let steps = 0
    const timer = setInterval(() => {
      for (const p of particles) {
        if (p.curR < p.targetR) p.curR++
        else if (p.curR > p.targetR) p.curR--
        if (p.curC < p.targetC) p.curC += Math.min(3, p.targetC - p.curC)
        else if (p.curC > p.targetC) p.curC -= Math.min(3, p.curC - p.targetC)
      }

      const g = makeGrid(" ")
      const co = makeColors("transparent")
      for (const p of particles) {
        const r = Math.max(0, Math.min(NUM_LINES - 1, p.curR))
        const c = Math.max(0, Math.min(g[r].length - 1, p.curC))
        g[r][c] = p.ch
        co[r][c] = p.color
      }
      setGrid(g)
      setColors(co)

      steps++
      if (steps > 30) {
        clearInterval(timer)
        setGrid(final)
        setColors(fc)
        setLabel("")
      }
    }, 50)

    return () => clearInterval(timer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 7: Typewriter + Cursor (FIXED — full completion) ──
function useTypewriter(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    setLabel("> █")
    setGrid(makeGrid(" "))
    setColors(makeColors(DIM))
    const final = finalGrid()
    const fc = finalColors()
    let charIndex = 0

    const timer = setInterval(() => {
      // Map linear charIndex to row/col
      let remaining = charIndex
      let row = 0
      let col = 0
      for (let r = 0; r < NUM_LINES; r++) {
        if (remaining < final[r].length) {
          row = r
          col = remaining
          break
        }
        remaining -= final[r].length
        if (r === NUM_LINES - 1) {
          row = NUM_LINES - 1
          col = final[r].length - 1
        }
      }

      if (charIndex >= TOTAL_CHARS) {
        clearInterval(timer)
        setGrid(final)
        setColors(fc)
        // Blink cursor
        let blinks = 0
        const blinkTimer = setInterval(() => {
          setLabel(blinks % 2 === 0 ? "> █" : "> ")
          blinks++
          if (blinks >= 5) {
            clearInterval(blinkTimer)
            setLabel("")
          }
        }, 300)
        return
      }

      setGrid(prev => {
        const next = prev.map(r => [...r])
        next[row][col] = final[row][col]
        return next
      })
      setColors(prev => {
        const next = prev.map(r => [...r])
        next[row][col] = fc[row][col]
        return next
      })

      charIndex++
    }, 4)

    return () => clearInterval(timer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 8: Glitch Flicker ──────────────────────────────────
function useGlitchFlicker(active: boolean) {
  const [grid, setGrid] = useState(finalGrid())
  const [colors, setColors] = useState(finalColors())
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    const final = finalGrid()
    const fc = finalColors()
    setGrid(final)
    setColors(fc)
    setLabel("")

    let glitchCount = 0
    const maxGlitches = 4
    let cancelled = false

    const scheduleGlitch = () => {
      const delay = 400 + Math.random() * 800
      setTimeout(() => {
        if (cancelled || glitchCount >= maxGlitches) return

        setColors(prev => prev.map((row) =>
          row.map((_, c) => {
            const shift = Math.floor(Math.random() * 3) - 1
            const sc = Math.max(0, Math.min(LINE_LEN - 1, c + shift))
            return sc < BLUE_LEN ? "hsl(217,91%,75%)" : "hsl(24,94%,70%)"
          })
        ))
        setGrid(prev => prev.map((row, r) => {
          if (Math.random() < 0.4) {
            const shift = Math.random() < 0.5 ? 1 : -1
            return row.map((_, c) => {
              const sc = c + shift
              return sc >= 0 && sc < row.length ? final[r][sc] : " "
            })
          }
          return [...row]
        }))

        setTimeout(() => {
          if (cancelled) return
          setGrid(final)
          setColors(fc)
          glitchCount++
          if (glitchCount < maxGlitches) scheduleGlitch()
        }, 80)
      }, delay)
    }

    scheduleGlitch()
    return () => { cancelled = true }
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 9: Cache Layer Scan ────────────────────────────────
function useCacheLayerScan(active: boolean) {
  const [grid, setGrid] = useState(finalGrid())
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    const final = finalGrid()
    const fc = finalColors()
    setGrid(final)
    setColors(makeColors(DIM))

    const layerNames = [
      "normalize", "composite_key", "exact_cache", "semantic",
      "composable", "fuzzy_match", "verify", "temporal", "metrics"
    ]
    const layerColors = [
      "#79c0ff", "#79c0ff", "#7ee787", "#7ee787",
      "#7ee787", "#ffa657", "#d2a8ff", "#d2a8ff", "#ff7b72"
    ]

    let layer = 0
    let scanRow = 0

    const timer = setInterval(() => {
      if (layer >= 9) {
        clearInterval(timer)
        setColors(fc)
        setLabel("[9/9] CACHE HIT")
        setTimeout(() => setLabel(""), 1000)
        return
      }

      setLabel(`[${layer + 1}/9] ${layerNames[layer]}`)

      setColors(prev => prev.map((row, r) =>
        row.map((_, c) => {
          if (r === scanRow) return layerColors[layer]
          if (r < scanRow) return fc[r][c]
          return DIM
        })
      ))

      scanRow++
      if (scanRow >= NUM_LINES) {
        scanRow = 0
        layer++
      }
    }, 60)

    return () => clearInterval(timer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 10: Pixel Rain (chars fall from top into place) ────
function usePixelRain(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    setLabel("// downloading cache")
    const final = finalGrid()
    const fc = finalColors()

    // Each column has a "drop" falling to its target rows
    type Drop = { col: number; targetRow: number; curRow: number; ch: string; color: string; landed: boolean }
    const drops: Drop[] = []
    for (let r = 0; r < NUM_LINES; r++) {
      for (let c = 0; c < final[r].length; c++) {
        if (final[r][c] !== " ") {
          drops.push({
            col: c, targetRow: r,
            curRow: -Math.floor(Math.random() * 12) - 1,
            ch: final[r][c], color: fc[r][c], landed: false,
          })
        }
      }
    }

    const timer = setInterval(() => {
      let allLanded = true
      for (const d of drops) {
        if (!d.landed) {
          d.curRow++
          if (d.curRow >= d.targetRow) {
            d.curRow = d.targetRow
            d.landed = true
          } else {
            allLanded = false
          }
        }
      }

      const g = makeGrid(" ")
      const co = makeColors("transparent")
      for (const d of drops) {
        if (d.curRow >= 0 && d.curRow < NUM_LINES) {
          g[d.curRow][d.col] = d.ch
          co[d.curRow][d.col] = d.landed ? d.color : GREEN
        }
      }
      setGrid(g)
      setColors(co)

      if (allLanded) {
        clearInterval(timer)
        setGrid(final)
        setColors(fc)
        setLabel("")
      }
    }, 45)

    return () => clearInterval(timer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 11: Encryption/Decryption ──────────────────────────
function useEncryptDecrypt(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    const final = finalGrid()
    const fc = finalColors()

    // Phase 1: show "encrypted" — scrambled with red tint
    setLabel("// encrypted: AES-256-GCM")
    setGrid(prev => prev.map(row => row.map(() => randomChar("▓░█╬╣╠╦╩■□"))))
    setColors(makeColors(RED))

    // Phase 2: decrypt row by row
    const t1 = setTimeout(() => {
      setLabel("// decrypting...")
      let currentRow = 0
      const timer = setInterval(() => {
        if (currentRow >= NUM_LINES) {
          clearInterval(timer)
          setGrid(final)
          setColors(fc)
          setLabel("// decrypted ✓")
          setTimeout(() => setLabel(""), 800)
          return
        }

        // Current row scrambles rapidly then resolves
        setGrid(prev => prev.map((row, r) => {
          if (r < currentRow) return [...final[r]]
          if (r === currentRow) return row.map((_, c) => c < final[r].length ? final[r][c] : " ")
          return row.map(() => randomChar("▓░█╬╣╠╦╩■□"))
        }))
        setColors(prev => prev.map((row, r) => {
          if (r < currentRow) return Array.from(final[r]).map((_, c) => fc[r][c])
          if (r === currentRow) return Array.from(final[r]).map((_, c) => fc[r][c])
          return row.map(() => RED)
        }))

        currentRow++
      }, 200)
    }, 1200)

    return () => clearTimeout(t1)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 12: Sonar Ping ─────────────────────────────────────
function useSonarPing(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    setLabel("// scanning network")
    const final = finalGrid()
    const fc = finalColors()
    setGrid(final)
    setColors(makeColors(DIM))

    // Multiple ping waves from random origins
    const origins = [
      { x: 0, y: 0 },
      { x: LINE_LEN - 1, y: NUM_LINES - 1 },
      { x: Math.floor(LINE_LEN / 2), y: Math.floor(NUM_LINES / 2) },
    ]
    let pingIndex = 0
    let radius = 0
    const revealed = Array.from({ length: NUM_LINES }, () => Array(LINE_LEN).fill(false))

    const timer = setInterval(() => {
      const origin = origins[pingIndex]
      radius += 2

      // Reveal chars within ring
      for (let r = 0; r < NUM_LINES; r++) {
        for (let c = 0; c < final[r].length; c++) {
          const dist = Math.sqrt((c - origin.x) ** 2 + ((r - origin.y) * 4) ** 2)
          if (dist <= radius && dist > radius - 4) {
            revealed[r][c] = true
          }
        }
      }

      setColors(prev => prev.map((row, r) =>
        row.map((_, c) => {
          if (!revealed[r]?.[c]) return DIM
          // Ring edge glows cyan
          const dist = Math.sqrt((c - origin.x) ** 2 + ((r - origin.y) * 4) ** 2)
          if (dist > radius - 4 && dist <= radius) return CYAN
          return fc[r][c]
        })
      ))

      if (radius > LINE_LEN * 1.5) {
        radius = 0
        pingIndex++
        if (pingIndex >= origins.length) {
          clearInterval(timer)
          setColors(fc)
          setLabel("")
        }
      }
    }, 30)

    return () => clearInterval(timer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 13: Boot Sequence ──────────────────────────────────
function useBootSequence(active: boolean) {
  const [grid, setGrid] = useState(makeGrid(" "))
  const [colors, setColors] = useState(makeColors(DIM))
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    const final = finalGrid()
    const fc = finalColors()
    setGrid(makeGrid(" "))

    const bootLines = [
      "BIOS: BitMod Cache Engine v0.2.0",
      "MEM:  checking local cache...",
      "NET:  connecting to peers...",
      "INIT: loading 9-layer pipeline...",
      "BOOT: ready.",
    ]

    let lineIdx = 0
    const bootTimer = setInterval(() => {
      if (lineIdx >= bootLines.length) {
        clearInterval(bootTimer)
        // Now reveal the wordmark with a flash
        setGrid(final)
        setColors(makeColors(WHITE))
        setTimeout(() => setColors(fc), 120)
        setTimeout(() => setLabel(""), 500)
        return
      }

      setLabel(bootLines[lineIdx])
      // Show progress bar in the grid
      const progress = (lineIdx + 1) / bootLines.length
      const fillCols = Math.floor(LINE_LEN * progress)
      setGrid(prev => prev.map((row, r) => {
        if (r === Math.floor(NUM_LINES / 2)) {
          return row.map((_, c) => c < fillCols ? "█" : "░")
        }
        if (r === Math.floor(NUM_LINES / 2) - 1) {
          return row.map((_, c) => c < fillCols ? "▓" : " ")
        }
        return row.map(() => " ")
      }))
      setColors(prev => prev.map((row, r) =>
        row.map((_, c) => c < fillCols ? GREEN : DIM)
      ))

      lineIdx++
    }, 500)

    return () => clearInterval(bootTimer)
  }, [active])

  return { grid, colors, label }
}

// ─── Animation 14: Heartbeat Pulse ────────────────────────────────
function useHeartbeatPulse(active: boolean) {
  const [grid, setGrid] = useState(finalGrid())
  const [colors, setColors] = useState(finalColors())
  const [label, setLabel] = useState("")

  useEffect(() => {
    if (!active) return
    const final = finalGrid()
    const fc = finalColors()
    setGrid(final)
    setColors(fc)
    setLabel("// heartbeat: alive")

    let beat = 0
    const maxBeats = 6

    const timer = setInterval(() => {
      if (beat >= maxBeats) {
        clearInterval(timer)
        setColors(fc)
        setLabel("")
        return
      }

      // Pulse: bright → dim → normal, emanating from center
      const phase = beat % 3
      const centerC = Math.floor(LINE_LEN / 2)

      if (phase === 0) {
        // Beat — everything pulses bright from center
        setColors(prev => prev.map((row, r) =>
          row.map((_, c) => {
            const dist = Math.abs(c - centerC)
            if (dist < 10) return WHITE
            if (dist < 20) return c < BLUE_LEN ? "hsl(217,91%,75%)" : "hsl(24,94%,68%)"
            return fc[r][c]
          })
        ))
      } else if (phase === 1) {
        // Expanding ring
        setColors(prev => prev.map((row, r) =>
          row.map((_, c) => {
            const dist = Math.abs(c - centerC)
            if (dist > 15 && dist < 25) return CYAN
            return fc[r][c]
          })
        ))
      } else {
        setColors(fc)
      }

      beat++
    }, 250)

    return () => clearInterval(timer)
  }, [active])

  return { grid, colors, label }
}

// ─── Main Component ───────────────────────────────────────────────

const ANIMATION_HOOKS = [
  useCacheHitCascade,    // 1
  useMatrixRainResolve,  // 2
  useBinaryDecode,       // 3
  useNetworkPropagation, // 4
  useQueryAnswerMorph,   // 5
  useDefragment,         // 6
  useTypewriter,         // 7
  useGlitchFlicker,      // 8
  useCacheLayerScan,     // 9
  usePixelRain,          // 10
  useEncryptDecrypt,     // 11
  useSonarPing,          // 12
  useBootSequence,       // 13
  useHeartbeatPulse,     // 14
]

const ANIMATION_NAMES = [
  "1: Cache Hit Cascade",
  "2: Matrix Rain Resolve",
  "3: Binary Decode",
  "4: Network Propagation",
  "5: Query → Answer Morph",
  "6: Defragment",
  "7: Typewriter + Cursor",
  "8: Glitch Flicker",
  "9: Cache Layer Scan",
  "10: Pixel Rain",
  "11: Encrypt/Decrypt",
  "12: Sonar Ping",
  "13: Boot Sequence",
  "14: Heartbeat Pulse",
]

const TOTAL_ANIMS = ANIMATION_HOOKS.length

function shuffleArray(arr: number[]): number[] {
  const shuffled = [...arr]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

function useRandomAnimCycle(interval: number) {
  const [order, setOrder] = useState<number[]>(() =>
    shuffleArray(Array.from({ length: TOTAL_ANIMS }, (_, i) => i))
  )
  const [pos, setPos] = useState(0)
  const [key, setKey] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setPos(prev => {
        const next = prev + 1
        if (next >= TOTAL_ANIMS) {
          // Reshuffle for next cycle
          setOrder(shuffleArray(Array.from({ length: TOTAL_ANIMS }, (_, i) => i)))
          setKey(k => k + 1)
          return 0
        }
        setKey(k => k + 1)
        return next
      })
    }, interval)
    return () => clearInterval(timer)
  }, [interval])

  return { currentAnim: order[pos] ?? 0, key }
}

function usePrefersReducedMotion() {
  const [prefersReduced, setPrefersReduced] = useState(false)

  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)")
    setPrefersReduced(mql.matches)
    const handler = (e: MediaQueryListEvent) => setPrefersReduced(e.matches)
    mql.addEventListener("change", handler)
    return () => mql.removeEventListener("change", handler)
  }, [])

  return prefersReduced
}

export function AnimatedWordmark({ className = "", showLabel = true }: { className?: string; showLabel?: boolean }) {
  const { currentAnim, key } = useRandomAnimCycle(5000)
  const prefersReducedMotion = usePrefersReducedMotion()

  if (prefersReducedMotion) {
    return (
      <div className={`flex flex-col items-center ${className}`}>
        <div className="font-mono text-[8px] sm:text-[10px] md:text-xs select-none">
          <RenderGrid grid={finalGrid()} colors={finalColors()} />
        </div>
      </div>
    )
  }

  return (
    <div className={`flex flex-col items-center ${className}`}>
      <div className="font-mono text-[8px] sm:text-[10px] md:text-xs select-none">
        <AnimationRenderer key={key} index={currentAnim} showLabel={showLabel} />
      </div>
      {showLabel && (
        <div className="mt-2 text-[10px] font-mono text-muted-foreground/50">
          {ANIMATION_NAMES[currentAnim]}
        </div>
      )}
    </div>
  )
}

// Smaller version for navbar — independent random order
export function AnimatedWordmarkNav({ className = "" }: { className?: string }) {
  const { currentAnim, key } = useRandomAnimCycle(5000)
  const prefersReducedMotion = usePrefersReducedMotion()

  if (prefersReducedMotion) {
    return (
      <div className={`font-mono text-[5px] sm:text-[6px] select-none ${className}`}>
        <RenderGrid grid={finalGrid()} colors={finalColors()} />
      </div>
    )
  }

  return (
    <div className={`font-mono text-[5px] sm:text-[6px] select-none ${className}`}>
      <AnimationRenderer key={key} index={currentAnim} showLabel={false} />
    </div>
  )
}

function AnimationRenderer({ index, showLabel = false }: { index: number; showLabel?: boolean }) {
  const a0 = useCacheHitCascade(index === 0)
  const a1 = useMatrixRainResolve(index === 1)
  const a2 = useBinaryDecode(index === 2)
  const a3 = useNetworkPropagation(index === 3)
  const a4 = useQueryAnswerMorph(index === 4)
  const a5 = useDefragment(index === 5)
  const a6 = useTypewriter(index === 6)
  const a7 = useGlitchFlicker(index === 7)
  const a8 = useCacheLayerScan(index === 8)
  const a9 = usePixelRain(index === 9)
  const a10 = useEncryptDecrypt(index === 10)
  const a11 = useSonarPing(index === 11)
  const a12 = useBootSequence(index === 12)
  const a13 = useHeartbeatPulse(index === 13)

  const anims = [a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13]
  const { grid, colors, label } = anims[index]

  return <RenderGrid grid={grid} colors={colors} label={label} showLabel={showLabel} />
}
