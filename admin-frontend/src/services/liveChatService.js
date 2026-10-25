import { ticketsApi } from '../api/tickets'

/** Ambil antrean dan statistik bersama; kegagalan statistik tidak menggagalkan daftar. */
export async function loadTicketQueue(activeTab, searchQuery) {
  const [ticketRes, statRes] = await Promise.all([
    ticketsApi.list({
      status: activeTab !== 'all' ? activeTab : undefined,
      search: searchQuery.trim() || undefined,
    }),
    ticketsApi.getStats().catch(() => null),
  ])

  return {
    tickets: ticketRes?.data || ticketRes?.tickets || (Array.isArray(ticketRes) ? ticketRes : []),
    stats: statRes?.data || statRes,
  }
}

/** Pertahankan dukungan respons pesan berbentuk data, messages, atau array langsung. */
export async function loadTicketMessages(ticketId) {
  const res = await ticketsApi.getMessages(ticketId)
  return res?.data || res?.messages || (Array.isArray(res) ? res : [])
}
