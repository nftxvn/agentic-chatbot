import * as React from "react"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-sky-500/20 bg-sky-500/10 text-sky-500 hover:bg-sky-500/20",
        secondary:
          "border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-secondary)]",
        destructive:
          "border-red-500/20 bg-red-500/10 text-red-500 hover:bg-red-500/20",
        outline: "text-[var(--text-primary)] border-[var(--border-color)]",
        success: "border-emerald-500/20 bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({ className, variant, ...props }) {
  return (
    <div
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
