import client from './client'

export const flowchartApi = {
  /**
   * Ambil data flowchart (nodes & edges) untuk dokumen tertentu.
   * Response shape: { success, data: { flowchart_data: { nodes, edges } | null, flowchart_status } }
   */
  async get(documentId) {
    const { data } = await client.get(`/api/documents/${documentId}/flowchart`)
    // Normalize: kembalikan nodes & edges langsung di data
    const flowchartData = data.data?.flowchart_data
    return {
      nodes: flowchartData?.nodes ?? [],
      edges: flowchartData?.edges ?? [],
      flowchart_status: data.data?.flowchart_status ?? 'draft',
    }
  },

  /**
   * Simpan nodes & edges flowchart (status tetap 'draft').
   */
  async save(documentId, nodes, edges) {
    const { data } = await client.put(`/api/documents/${documentId}/flowchart`, {
      nodes,
      edges,
    })
    return data
  },

  /**
   * Finalize flowchart: konversi ke markdown lalu re-embed ke ChromaDB.
   */
  async finalize(documentId) {
    const { data } = await client.post(`/api/documents/${documentId}/flowchart/finalize`)
    return data
  },
}
