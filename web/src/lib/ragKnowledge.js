/* ============================================================
   RAG knowledge base — Turkish accounting / tax / SGK facts.
   Retrieved client-side to ground the assistant when it answers locally.
   (Informational; rates are illustrative for the 2026 demo.)
   ============================================================ */

export const KNOWLEDGE_DOCS = {
  kdv_oranlari: {
    id: 'kdv_oranlari',
    title: 'KDV Oranları (2026)',
    tags: ['kdv', 'vergi', 'oran', 'tevkifat', 'vat', 'tax'],
    content:
      'Türkiye’de 2026 itibarıyla üç temel KDV oranı uygulanır: genel oran %20, indirimli oran %10 (gıda, tekstil, bazı hizmetler) ve süper indirimli oran %1 (temel gıda, gazete, bazı tarım ürünleri). KDV, mal/hizmet bedeli üzerinden hesaplanır ve aylık KDV beyannamesi ile takip eden ayın 28’ine kadar beyan edilip ödenir.',
  },
  kdv_iadesi: {
    id: 'kdv_iadesi',
    title: 'KDV İadesi Şartları',
    tags: ['kdv', 'iade', 'ihracat', 'indirim', 'refund', 'vat'],
    content:
      'KDV iadesi genellikle ihracat, indirimli orana tabi teslimler ve tevkifat uygulanan işlemlerde doğar. İade için yüklenilen KDV’nin hesaplanan KDV’den fazla olması, belgelerin (fatura, gümrük beyannamesi) eksiksiz olması ve YMM raporu ya da teminat gerekebilir. Mahsuben iade kendi vergi borçlarına, nakden iade ise banka hesabına yapılır.',
  },
  sgk_primleri: {
    id: 'sgk_primleri',
    title: 'SGK Prim Oranları',
    tags: ['sgk', 'prim', 'bordro', 'sigorta', 'işveren', 'payroll', 'premium'],
    content:
      'SGK primi brüt ücret üzerinden hesaplanır. Toplam prim oranı %37,5’tir: çalışan payı %14 + işsizlik %1 = %15, işveren payı %20,5 + işsizlik %2 = %22,5. 5 puanlık işveren indirimi (5510 sayılı Kanun) ile düzenli ödeyen işverenlerde işveren payı efektif düşebilir. Prime esas kazancın 2026 alt sınırı asgari ücret, üst sınırı bunun 7,5 katıdır.',
  },
  bordro_hesaplama: {
    id: 'bordro_hesaplama',
    title: 'Bordro Hesaplama Adımları',
    tags: ['bordro', 'maaş', 'net', 'brüt', 'kesinti', 'payroll', 'salary'],
    content:
      'Net maaş hesabı: Brüt ücretten önce SGK çalışan primi (%14) ve işsizlik (%1) düşülür. Kalan tutar gelir vergisi matrahıdır; gelir vergisi dilimine (%15’ten başlayan artan oranlı) göre vergi hesaplanır. Ayrıca damga vergisi (binde 7,59) düşülür. Asgari ücret gelir vergisi ve damga vergisinden istisnadır. Geriye kalan tutar net maaştır.',
  },
  gelir_vergisi_dilimleri: {
    id: 'gelir_vergisi_dilimleri',
    title: 'Gelir Vergisi Dilimleri (2026)',
    tags: ['gelir vergisi', 'dilim', 'oran', 'matrah', 'income tax'],
    content:
      'Gelir vergisi artan oranlıdır ve %15, %20, %27, %35, %40 dilimlerinden oluşur. Ücret gelirlerinde dilimler daha yüksek tutarlardan başlar. Vergi, kümülatif matrah üzerinden hesaplanır; yıl içinde matrah arttıkça çalışan üst dilime geçebilir ve net maaşı bir miktar düşebilir.',
  },
  e_beyanname: {
    id: 'e_beyanname',
    title: 'e-Beyanname ve Beyan Takvimi',
    tags: ['beyanname', 'e-beyanname', 'kdv', 'muhtasar', 'takvim', 'filing'],
    content:
      'e-Beyanname, beyannamelerin GİB sistemi üzerinden elektronik gönderimidir. KDV beyannamesi takip eden ayın 28’ine kadar; Muhtasar ve Prim Hizmet Beyannamesi (SGK ile birleşik) yine ayın 26’sı/28’i civarında verilir. Geçici vergi üç ayda bir beyan edilir. Süresinde verilmeyen beyannameler için usulsüzlük cezası uygulanır.',
  },
  e_fatura: {
    id: 'e_fatura',
    title: 'e-Fatura ve e-Arşiv',
    tags: ['e-fatura', 'fatura', 'e-arşiv', 'gib', 'invoice'],
    content:
      'Belirli ciro eşiğini aşan mükellefler e-Fatura ve e-Arşiv Fatura kullanmak zorundadır. e-Fatura kayıtlı kullanıcılar arasında, e-Arşiv ise kayıtlı olmayan alıcılara düzenlenir. Faturalar GİB onaylı entegratör veya portal üzerinden iletilir. Muhai OCR motoru kağıt/PDF faturaları okuyup bu kalemleri otomatik ayrıştırır.',
  },
  stopaj: {
    id: 'stopaj',
    title: 'Stopaj (Tevkifat)',
    tags: ['stopaj', 'tevkifat', 'kira', 'serbest meslek', 'withholding'],
    content:
      'Stopaj, ödeme yapılırken kaynağında kesilen vergidir. Örneğin iş yeri kira ödemelerinde %20, serbest meslek ödemelerinde %20 stopaj uygulanır. Kesilen stopaj muhtasar beyanname ile beyan edilir ve ödenir. Stopaj, yıllık gelir/kurumlar vergisinden mahsup edilebilir.',
  },
  kobi_destek: {
    id: 'kobi_destek',
    title: 'KOBİ Destekleri ve Teşvikler',
    tags: ['kobi', 'teşvik', 'destek', 'kosgeb', 'sme', 'incentive'],
    content:
      'KOBİ’ler KOSGEB destekleri, yatırım teşvik belgesi, Ar-Ge indirimi ve istihdam teşviklerinden yararlanabilir. İlave istihdamda SGK işveren prim desteği, genç ve kadın istihdamında ek teşvikler sağlanır. Yatırım teşvik belgesi ile KDV istisnası ve gümrük muafiyeti mümkündür.',
  },
  nakit_akisi: {
    id: 'nakit_akisi',
    title: 'Nakit Akışı Yönetimi',
    tags: ['nakit akışı', 'cash flow', 'likidite', 'tahsilat', 'kârlılık', 'profit'],
    content:
      'Sağlıklı nakit akışı için tahsilat sürelerini kısaltmak, ödeme vadelerini dengelemek ve düzenli nakit akış tablosu tutmak önemlidir. Kârlılığı artırmak için yüksek marjlı ürünlere odaklanmak, sabit giderleri gözden geçirmek ve stok devir hızını yükseltmek etkilidir. Muhai paneli gelir-gider trendini ve kategori dağılımını canlı gösterir.',
  },
  amortisman: {
    id: 'amortisman',
    title: 'Amortisman',
    tags: ['amortisman', 'demirbaş', 'sabit kıymet', 'depreciation'],
    content:
      'Amortisman, sabit kıymetlerin (demirbaş, makine, taşıt) faydalı ömrü boyunca giderleştirilmesidir. Normal veya azalan bakiye yöntemiyle hesaplanır. 2026 için belirlenen tutarın altındaki demirbaşlar doğrudan gider yazılabilir. Amortisman, vergi matrahını düşürerek vergi avantajı sağlar.',
  },
  damga_vergisi: {
    id: 'damga_vergisi',
    title: 'Damga Vergisi',
    tags: ['damga vergisi', 'sözleşme', 'bordro', 'stamp tax'],
    content:
      'Damga vergisi sözleşme, bordro, ihale kararı gibi kağıtlar üzerinden alınır. Ücret bordrolarında binde 7,59 oranında uygulanır (asgari ücret istisna kapsamındadır). Sözleşmelerde bedelin binde 9,48’i oranında damga vergisi doğar.',
  },
}

/* Lightweight Turkish-aware tokenizer */
const TR_LOWER = (s) =>
  s
    .replace(/I/g, 'ı')
    .replace(/İ/g, 'i')
    .toLowerCase()

const STOP = new Set([
  've', 'ile', 'için', 'bir', 'bu', 'mi', 'mı', 'nasıl', 'nedir', 'ne', 'da', 'de', 'the', 'a', 'an',
  'is', 'are', 'how', 'what', 'of', 'to', 'in', 'on', 'my', 'i', 'do', 'does',
])

function tokenize(text) {
  return TR_LOWER(text)
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOP.has(w))
}

/**
 * Retrieve the top-k most relevant knowledge docs for a query.
 * Scoring: tag hits (weighted) + title/content token overlap.
 */
export function retrieve(query, docsObj, k = 3) {
  const docs = Object.values(docsObj || {})
  if (!docs.length) return []
  const qTokens = tokenize(query)
  const qSet = new Set(qTokens)
  const qJoined = TR_LOWER(query)

  const scored = docs.map((doc) => {
    let score = 0
    // tag matches are strong signals
    for (const tag of doc.tags || []) {
      if (qJoined.includes(TR_LOWER(tag))) score += 5
      for (const t of tokenize(tag)) if (qSet.has(t)) score += 3
    }
    // title overlap
    for (const t of tokenize(doc.title)) if (qSet.has(t)) score += 2
    // content overlap
    const contentTokens = tokenize(doc.content)
    const cSet = new Set(contentTokens)
    let overlap = 0
    for (const t of qSet) if (cSet.has(t)) overlap += 1
    score += overlap
    return { doc, score }
  })

  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map((s) => s.doc)
}
