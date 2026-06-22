export function TerminalLogo({ className = "" }: { className?: string }) {
  return (
    <div className={`font-mono text-[10px] sm:text-xs md:text-sm leading-[1.1] select-none ${className}`}>
      <pre className="inline-block text-left">
        <span className="text-[hsl(217,91%,60%)]">{`        ██████████▓▓                    `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`      ████████████████▓                 `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`    ████▓░░░░░░░██████▓                 `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`   ████░          ░████`}</span><span className="text-[hsl(24,94%,53%)]">{`▓▓▓▓▓▓▓▓▓▓      `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`  ████░            ░███`}</span><span className="text-[hsl(24,94%,53%)]">{`██████████▓▓    `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`  ████░            ░░░░`}</span><span className="text-[hsl(24,94%,53%)]">{`░░░░░░██████▓   `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`  ████░                `}</span><span className="text-[hsl(24,94%,53%)]">{`        ░█████  `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`  ████▓░░░░░░░░░       `}</span><span className="text-[hsl(24,94%,53%)]">{`         ░████  `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`   █████████████▓░     `}</span><span className="text-[hsl(24,94%,53%)]">{`         ░████  `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`     ░░░░░░██████▓░    `}</span><span className="text-[hsl(24,94%,53%)]">{`         ░████  `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`            ░█████▓    `}</span><span className="text-[hsl(24,94%,53%)]">{`░░░░░░░░░█████  `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`             ░█████`}</span><span className="text-[hsl(24,94%,53%)]">{`░░░░████████████▓   `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`             ░████`}</span><span className="text-[hsl(24,94%,53%)]">{`██████████████▓▓    `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`            ░████`}</span><span className="text-[hsl(24,94%,53%)]">{`█░          ░████   `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`  ████░    ░████`}</span><span className="text-[hsl(24,94%,53%)]">{`█░            ████  `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`  ████░   ░████`}</span><span className="text-[hsl(24,94%,53%)]">{`█▓░            ████  `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`  █████░░█████`}</span><span className="text-[hsl(24,94%,53%)]">{`█▓░░            ████  `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`   ██████████`}</span><span className="text-[hsl(24,94%,53%)]">{`█▓░░░░░░░░░░░░█████  `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`    ▓████████`}</span><span className="text-[hsl(24,94%,53%)]">{`██████████████████   `}</span>{"\n"}
        <span className="text-[hsl(24,94%,53%)]">{`               ▓██████████████▓    `}</span>{"\n"}
        <span className="text-[hsl(24,94%,53%)]">{`                 ▓▓████████▓▓      `}</span>
      </pre>
    </div>
  )
}

export function TerminalWordmark({ className = "" }: { className?: string }) {
  return (
    <div className={`font-mono text-[8px] sm:text-[10px] md:text-xs leading-[1.15] select-none ${className}`}>
      <pre className="inline-block text-left">
        <span className="text-[hsl(217,91%,60%)]">{`██████╗  ██╗████████╗`}</span><span className="text-[hsl(24,94%,53%)]">{`███╗   ███╗ ██████╗ ██████╗ `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`██╔══██╗ ██║╚══██╔══╝`}</span><span className="text-[hsl(24,94%,53%)]">{`████╗ ████║██╔═══██╗██╔══██╗`}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`██████╔╝ ██║   ██║   `}</span><span className="text-[hsl(24,94%,53%)]">{`██╔████╔██║██║   ██║██║  ██║`}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`██╔══██╗ ██║   ██║   `}</span><span className="text-[hsl(24,94%,53%)]">{`██║╚██╔╝██║██║   ██║██║  ██║`}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`██████╔╝ ██║   ██║   `}</span><span className="text-[hsl(24,94%,53%)]">{`██║ ╚═╝ ██║╚██████╔╝██████╔╝`}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`╚═════╝  ╚═╝   ╚═╝   `}</span><span className="text-[hsl(24,94%,53%)]">{`╚═╝     ╚═╝ ╚═════╝ ╚═════╝ `}</span>
      </pre>
    </div>
  )
}

export function TerminalWordmarkInline({ className = "" }: { className?: string }) {
  return (
    <span className={`font-mono text-[10px] sm:text-xs leading-none select-none tracking-tight ${className}`}>
      <span className="text-[hsl(217,91%,60%)] font-bold">▌Bit</span><span className="text-[hsl(24,94%,53%)] font-bold">Mod▐</span>
    </span>
  )
}

export function TerminalWordmarkNav({ className = "" }: { className?: string }) {
  return (
    <div className={`font-mono text-[5px] sm:text-[6px] leading-[1.15] select-none ${className}`}>
      <pre className="inline-block text-left">
        <span className="text-[hsl(217,91%,60%)]">{`██████╗ ██╗████████╗`}</span><span className="text-[hsl(24,94%,53%)]">{`███╗   ███╗ ██████╗ ██████╗ `}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`██╔══██╗██║╚══██╔══╝`}</span><span className="text-[hsl(24,94%,53%)]">{`████╗ ████║██╔═══██╗██╔══██╗`}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`██████╔╝██║   ██║   `}</span><span className="text-[hsl(24,94%,53%)]">{`██╔████╔██║██║   ██║██║  ██║`}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`██╔══██╗██║   ██║   `}</span><span className="text-[hsl(24,94%,53%)]">{`██║╚██╔╝██║██║   ██║██║  ██║`}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`██████╔╝██║   ██║   `}</span><span className="text-[hsl(24,94%,53%)]">{`██║ ╚═╝ ██║╚██████╔╝██████╔╝`}</span>{"\n"}
        <span className="text-[hsl(217,91%,60%)]">{`╚═════╝ ╚═╝   ╚═╝   `}</span><span className="text-[hsl(24,94%,53%)]">{`╚═╝     ╚═╝ ╚═════╝ ╚═════╝ `}</span>
      </pre>
    </div>
  )
}

export function TerminalLogoFull({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-col items-center ${className}`}>
      <TerminalWordmark />
    </div>
  )
}
