export const mockChatStream = async function* (message) {
  const answer = `[MOCK] Jawaban untuk: "${message}". Ini adalah simulasi streaming dari mock API lokal karena Dev 1 belum siap.`;
  const sources = [
    { doc_name: 'Panduan_IT_Support.pdf', page: 5 },
    { doc_name: 'Kebijakan_Jaringan_2024.pdf', page: 2 }
  ];

  // Simulasi delay awal (mikir)
  await new Promise(res => setTimeout(res, 800));

  // Simulasi streaming per kata
  const words = answer.split(' ');
  for (const word of words) {
    await new Promise(res => setTimeout(res, 50));
    yield { type: 'chunk', chunk: word + ' ' };
  }

  // Kirim source di akhir streaming
  yield { type: 'sources', sources };
};
