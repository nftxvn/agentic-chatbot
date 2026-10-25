import * as React from "react"
import { cn } from "@/lib/utils"

function Input({ className, type, onInvalid, onInput, ...props }) {
  const handleInvalid = (e) => {
    const el = e.target
    if (el.validity.valueMissing) {
      el.setCustomValidity("Bidang ini wajib diisi.")
    } else if (el.validity.typeMismatch && el.type === "email") {
      el.setCustomValidity("Harap masukkan alamat email yang valid.")
    } else if (el.validity.typeMismatch && el.type === "url") {
      el.setCustomValidity("Harap masukkan URL yang valid.")
    } else if (el.validity.tooShort) {
      el.setCustomValidity(`Panjang teks minimal ${el.minLength} karakter.`)
    } else {
      el.setCustomValidity("Isian tidak valid.")
    }
    if (onInvalid) onInvalid(e)
  }

  const handleInput = (e) => {
    e.target.setCustomValidity("")
    if (onInput) onInput(e)
  }

  return (
    <input
      type={type}
      data-slot="input"
      onInvalid={handleInvalid}
      onInput={handleInput}
      className={cn(
        "w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] transition-all placeholder:text-[var(--text-muted)] focus:bg-[var(--bg-input)] focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Input }
