import * as React from "react"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-[var(--border-color)] bg-[var(--bg-input)] text-sky-600 dark:text-sky-400 hover:bg-[var(--border-color)]",
        secondary:
          "border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-secondary)]",
        destructive:
          "border-[var(--border-color)] bg-[var(--bg-input)] text-red-600 dark:text-red-400 hover:bg-[var(--border-color)]",
        outline: "text-[var(--text-primary)] border-[var(--border-color)]",
        success: "border-[var(--border-color)] bg-[var(--bg-input)] text-emerald-600 dark:text-emerald-400 hover:bg-[var(--border-color)]",
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
