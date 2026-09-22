/**
 * Inisialisasi lokalisasi pesan validasi form bawaan browser (HTML5 Validation Tooltip)
 * ke Bahasa Indonesia.
 *
 * Mengubah tooltip default browser seperti "Please fill out this field."
 * menjadi "Bidang ini wajib diisi." secara konsisten di semua browser.
 */
export function initFormValidationLocalization() {
  if (typeof window === 'undefined' || typeof document === 'undefined') return

  // Tangkap event invalid pada fase capture
  document.addEventListener(
    'invalid',
    (event) => {
      const el = event.target
      if (!el || !el.validity) return

      // Bersihkan custom validity sebelumnya terlebih dahulu
      el.setCustomValidity('')

      if (el.validity.valueMissing) {
        if (el.type === 'checkbox' || el.type === 'radio') {
          el.setCustomValidity('Harap centang atau pilih opsi ini.')
        } else if (el.tagName === 'SELECT') {
          el.setCustomValidity('Harap pilih salah satu opsi dalam daftar.')
        } else if (el.type === 'file') {
          el.setCustomValidity('Harap pilih berkas untuk diunggah.')
        } else {
          el.setCustomValidity('Bidang ini wajib diisi.')
        }
      } else if (el.validity.typeMismatch) {
        if (el.type === 'email') {
          el.setCustomValidity('Harap masukkan alamat email yang valid.')
        } else if (el.type === 'url') {
          el.setCustomValidity('Harap masukkan alamat tautan (URL) yang valid.')
        } else {
          el.setCustomValidity('Format yang dimasukkan tidak sesuai.')
        }
      } else if (el.validity.tooShort) {
        el.setCustomValidity(
          `Panjang teks minimal ${el.minLength} karakter (saat ini ${el.value.length} karakter).`
        )
      } else if (el.validity.tooLong) {
        el.setCustomValidity(`Panjang teks maksimal ${el.maxLength} karakter.`)
      } else if (el.validity.patternMismatch) {
        el.setCustomValidity('Format yang Anda masukkan tidak sesuai dengan pola yang diminta.')
      } else if (el.validity.rangeUnderflow) {
        el.setCustomValidity(`Nilai minimal adalah ${el.min}.`)
      } else if (el.validity.rangeOverflow) {
        el.setCustomValidity(`Nilai maksimal adalah ${el.max}.`)
      } else if (el.validity.stepMismatch) {
        el.setCustomValidity('Nilai yang dimasukkan tidak sesuai dengan interval langkah.')
      } else if (el.validity.badInput) {
        el.setCustomValidity('Harap masukkan nilai yang valid.')
      }
    },
    true
  )

  // Reset pesan kustom saat pengguna mulai mengetik atau mengubah input
  const resetValidity = (event) => {
    const el = event.target
    if (el && typeof el.setCustomValidity === 'function') {
      el.setCustomValidity('')
    }
  }

  document.addEventListener('input', resetValidity, true)
  document.addEventListener('change', resetValidity, true)
}
