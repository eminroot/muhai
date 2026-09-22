"""Local Turkish accounting/finance knowledge base for the offline assistant.

These passages are the retrieval corpus behind `OfflineRagBackend`. They are
deliberately short and self-contained: each one should stand on its own as an
answer, because retrieval returns whole passages, not sentences.

Every rate is interpolated from `tax_service` rather than typed in as a
literal. The knowledge base cannot drift out of step with the engine that
actually does the arithmetic — change a rate there and the assistant's wording
follows.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services import tax_service as tax


def _pct(rate: float) -> str:
    """0.195 -> '%19,5' — Turkish formatting, no trailing zeros."""
    text = f"{rate * 100:.3f}".rstrip("0").rstrip(".")
    return "%" + text.replace(".", ",")


@dataclass(frozen=True)
class Doc:
    """One retrievable passage."""

    id: str
    title: str
    text: str
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def indexed_text(self) -> str:
        """Title and tags are repeated so they weigh more than body prose."""
        return f"{self.title} {' '.join(self.tags)} {self.title} {self.text}"


_INCOME_BRACKETS = "; ".join(
    f"{limit:,.0f} ₺'ye kadar {_pct(rate)}".replace(",", ".")
    if limit != float("inf")
    else f"üzeri {_pct(rate)}"
    for limit, rate in tax.INCOME_TAX_BRACKETS
)


DOCS: tuple[Doc, ...] = (
    Doc(
        id="kdv-oranlari",
        title="KDV oranları ve hesaplama",
        tags=("kdv", "katma değer vergisi", "vat", "oran", "hesaplama"),
        text=(
            f"Türkiye'de standart KDV oranı {_pct(tax.VAT_STANDARD)}'dir. "
            f"İndirimli oran {_pct(tax.VAT_REDUCED)} (tekstil, otel, sinema gibi), "
            f"temel gıda ve kitap gibi ürünlerde {_pct(tax.VAT_BASIC)} uygulanır. "
            "KDV net tutar üzerinden hesaplanır: KDV = net × oran. "
            "Fiyat KDV dahil verilmişse net tutar = brüt ÷ (1 + oran) ile bulunur. "
            "Ödenecek KDV, satışlarınızdan tahsil ettiğiniz hesaplanan KDV'den "
            "alışlarınızda ödediğiniz indirilecek KDV'nin düşülmesiyle bulunur; "
            "sonuç negatifse devreden KDV olarak sonraki aya taşınır."
        ),
    ),
    Doc(
        id="kdv-beyanname",
        title="KDV beyannamesi ve ödeme takvimi",
        tags=("kdv", "beyanname", "takvim", "son tarih", "ödeme"),
        text=(
            "KDV beyannamesi aylık dönemler hâlinde verilir. Beyanname, izleyen "
            "ayın 28'ine kadar verilir ve vergi aynı gün içinde ödenir. "
            "Beyannameyi zamanında vermemek usulsüzlük cezası, vergiyi geç ödemek "
            "ise gecikme zammı doğurur. Muhai'de yaklaşan yükümlülükleri Vergi "
            "sekmesindeki takvimden takip edebilirsiniz."
        ),
    ),
    Doc(
        id="gelir-vergisi",
        title="Gelir vergisi dilimleri",
        tags=("gelir vergisi", "vergi dilimi", "şahıs şirketi", "stopaj matrahı"),
        text=(
            "Gelir vergisi artan oranlıdır: kazanç yükseldikçe üst dilimin oranı "
            f"yalnızca o dilime düşen kısma uygulanır. Dilimler: {_INCOME_BRACKETS}. "
            "Şahıs şirketleri ve serbest meslek kazançları gelir vergisine tabidir; "
            "sermaye şirketleri ise kurumlar vergisi öder."
        ),
    ),
    Doc(
        id="kurumlar-vergisi",
        title="Kurumlar vergisi",
        tags=("kurumlar vergisi", "limited", "anonim", "şirket", "kâr"),
        text=(
            f"Kurumlar vergisi genel oranı {_pct(tax.CORPORATE_TAX_RATE)}'tir. "
            f"Banka, sigorta ve petrol şirketlerinde {_pct(tax.CORPORATE_TAX_RATE_FINANCIAL)}, "
            "ihracat kazançlarına isabet eden kısımda ise "
            f"{_pct(tax.CORPORATE_TAX_RATE_EXPORTER)} uygulanır. "
            "Matrah, ticari kârdan kanunen kabul edilmeyen giderler eklenip "
            "istisnalar düşülerek bulunur. Yıl içinde geçici (peşin) vergi ödenir, "
            "yıl sonunda mahsup edilir."
        ),
    ),
    Doc(
        id="stopaj",
        title="Stopaj (kaynakta kesinti)",
        tags=("stopaj", "kira", "serbest meslek", "kesinti", "muhtasar"),
        text=(
            "Stopaj, ödemeyi yapanın vergiyi kaynağında kesip vergi dairesine "
            "yatırmasıdır. İş yeri kira ödemelerinde "
            f"{_pct(tax.STOPAJ_RATES.get('rent', 0.20))}, serbest meslek "
            f"ödemelerinde {_pct(tax.STOPAJ_RATES.get('freelance', 0.20))} "
            "oranı yaygın olarak uygulanır. Kesilen tutarlar muhtasar beyanname "
            "ile bildirilir. Kiracı olarak brüt kira üzerinden stopaj keser, net "
            "tutarı mal sahibine ödersiniz."
        ),
    ),
    Doc(
        id="sgk-primleri",
        title="SGK primleri ve işveren yükü",
        tags=("sgk", "prim", "işveren", "işçi", "sigorta", "işsizlik"),
        text=(
            f"SGK işçi payı brüt maaşın {_pct(tax.SGK_EMPLOYEE_RATE)}'ü, işsizlik "
            f"sigortası işçi payı {_pct(tax.UNEMPLOYMENT_EMPLOYEE_RATE)}'dir; ikisi "
            "de çalışanın brütünden kesilir. İşveren tarafında SGK payı "
            f"{_pct(tax.SGK_EMPLOYER_RATE)}, işsizlik işveren payı "
            f"{_pct(tax.UNEMPLOYMENT_EMPLOYER_RATE)}'dir ve bunlar maaşın üstüne "
            "eklenen ek maliyettir. Primler izleyen ayın sonuna kadar ödenir."
        ),
    ),
    Doc(
        id="bordro",
        title="Net maaş ve bordro hesabı",
        tags=("bordro", "maaş", "net", "brüt", "ücret", "damga"),
        text=(
            "Net maaş, brüt maaştan SGK işçi payı "
            f"({_pct(tax.SGK_EMPLOYEE_RATE)}), işsizlik payı "
            f"({_pct(tax.UNEMPLOYMENT_EMPLOYEE_RATE)}), gelir vergisi ve damga "
            f"vergisi ({_pct(tax.STAMP_PAYROLL_RATE)}) düşülerek bulunur. "
            "Gelir vergisi matrahı, brütten SGK ve işsizlik kesintileri "
            "düşüldükten sonra kalan tutardır; yıl içinde kümülatif matrah "
            "büyüdükçe çalışan üst vergi dilimine geçer ve net maaş yıl sonuna "
            "doğru düşer. Bu, hata değil beklenen davranıştır."
        ),
    ),
    Doc(
        id="damga-vergisi",
        title="Damga vergisi",
        tags=("damga vergisi", "sözleşme", "kağıt"),
        text=(
            f"Damga vergisi ücret ödemelerinde {_pct(tax.STAMP_PAYROLL_RATE)}, "
            f"sözleşmelerde sözleşme bedelinin {_pct(tax.STAMP_CONTRACT_RATE)}'i "
            "oranında hesaplanır. Sözleşmenin her nüshası ayrı ayrı vergiye "
            "tabidir; tek nüsha düzenlemek maliyeti azaltır."
        ),
    ),
    Doc(
        id="calisan-maliyeti",
        title="Bir çalışanın işverene toplam maliyeti",
        tags=("işe alım", "çalışan maliyeti", "eleman", "istihdam", "bordro maliyeti"),
        text=(
            "Bir çalışanın işverene maliyeti brüt maaşın kendisi değildir: brüt "
            f"maaşa SGK işveren payı ({_pct(tax.SGK_EMPLOYER_RATE)}) ve işsizlik "
            f"işveren payı ({_pct(tax.UNEMPLOYMENT_EMPLOYER_RATE)}) eklenir, yani "
            f"toplam maliyet brütün yaklaşık "
            f"{_pct(1 + tax.SGK_EMPLOYER_RATE + tax.UNEMPLOYMENT_EMPLOYER_RATE)}'ine "
            "denk gelir. İşe alım kararında bu toplam maliyeti en az 6 aylık nakit "
            "rezerviyle birlikte değerlendirin."
        ),
    ),
    Doc(
        id="nakit-akisi",
        title="Nakit akışı yönetimi",
        tags=("nakit", "nakit akışı", "likidite", "kasa", "runway"),
        text=(
            "Kârlı bir işletme bile nakit yönetimi zayıfsa ödeme güçlüğüne düşer: "
            "kâr tahakkuk, nakit ise tahsilat esaslıdır. Nakit rezervinizi aylık "
            "sabit giderinize bölerek kaç ay dayanabileceğinizi bulun; 3 ayın "
            "altı riskli, 6 ay ve üzeri güvenlidir. Tahsilat vadelerinizi ödeme "
            "vadelerinizden kısa tutmak nakit döngüsünü rahatlatır."
        ),
    ),
    Doc(
        id="alacak-yonetimi",
        title="Alacak ve tahsilat yönetimi",
        tags=("alacak", "tahsilat", "vade", "ödenmemiş fatura", "borçlu"),
        text=(
            "Vadesi geçmiş alacaklar, işletme sermayenizin müşteride bekleyen "
            "kısmıdır. Tahsilatı hızlandırmak için: vadeden birkaç gün önce "
            "hatırlatma gönderin, erken ödemeye küçük bir iskonto tanımlayın, "
            "büyük işlerde peşinat alın ve sürekli geciken müşterilere vadeli "
            "satışı kısın. Vadesi 90 günü aşan alacakların tahsil edilebilirliği "
            "belirgin şekilde düşer."
        ),
    ),
    Doc(
        id="stok-yonetimi",
        title="Stok yönetimi ve kritik seviye",
        tags=("stok", "envanter", "ürün", "kritik stok", "tedarik"),
        text=(
            "Her ürün için kritik stok seviyesi, tedarik süresi boyunca beklenen "
            "satış miktarına eşit olmalıdır. Bu seviyenin altına düşen ürünler "
            "satış kaybı riski taşır. Fazla stok ise nakdi rafta bekletir ve "
            "depolama maliyeti doğurur. Stok devir hızı = satılan malın maliyeti "
            "÷ ortalama stok; hız yükseldikçe aynı sermaye daha çok ciro üretir."
        ),
    ),
    Doc(
        id="karlilik",
        title="Kârlılık, marj ve başabaş noktası",
        tags=("kâr", "kârlılık", "marj", "başabaş", "brüt kâr"),
        text=(
            "Brüt kâr marjı = (gelir − satılan malın maliyeti) ÷ gelir. Net kâr "
            "marjı ise tüm giderler ve vergiler düşüldükten sonra kalan orandır. "
            "Başabaş noktası = sabit giderler ÷ brüt kâr marjı; bu ciroya "
            "ulaşmadan kâr oluşmaz. Marjı ölçmeden ciro büyütmek, zararı "
            "büyütmek anlamına gelebilir."
        ),
    ),
    Doc(
        id="kar-artirma",
        title="Kârı artırmanın yolları",
        tags=(
            "kâr artırma", "ekstra kâr", "kârı artır", "gelir artırma",
            "gider azaltma", "büyüme", "öneri", "tavsiye",
        ),
        text=(
            "Kâr yalnızca dört koldan artar: fiyatı yükseltmek, satış hacmini "
            "büyütmek, birim maliyeti düşürmek, sabit gideri azaltmak. "
            "Bunlar arasında en hızlı etki eden genellikle fiyattır — "
            "%1'lik fiyat artışı, %1'lik hacim artışından daha çok kâr üretir, "
            "çünkü ek maliyet doğurmaz. Uygulamada sırasıyla şunlara bakın: "
            "vadesi geçmiş alacakları tahsil edin (bu nakit, yeni satış gerektirmez); "
            "en yüksek gider kalemlerinizi tek tek gözden geçirin; düşük marjlı "
            "ürünleri ya fiyatlandırın ya bırakın; stok tükenmesi yüzünden "
            "kaçırdığınız satışları önleyin; tedarikçi sözleşmelerini yeniden "
            "pazarlık edin."
        ),
    ),
    Doc(
        id="fiyatlandirma",
        title="Fiyatlandırma",
        tags=("fiyat", "fiyatlandırma", "zam", "iskonto"),
        text=(
            "Maliyet artı yöntemi (maliyet × 1 + hedef marj) tabanı belirler, "
            "ancak fiyatı piyasa ve algılanan değer tayin eder. Zam yaparken "
            "tüm portföye aynı oranı uygulamak yerine, talebi fiyata az duyarlı "
            "ürünlerde daha yüksek artış yapın. Küçük ve düzenli artışlar, "
            "seyrek ve büyük artışlardan daha az müşteri kaybettirir."
        ),
    ),
    Doc(
        id="gider-kategorileri",
        title="Gider kategorileri ve indirilebilirlik",
        tags=("gider", "masraf", "harcama", "indirim", "kanunen kabul edilmeyen"),
        text=(
            "Bir giderin vergi matrahından düşülebilmesi için işle doğrudan "
            "ilgili ve belgeli olması gerekir. Faturasız harcamalar, işletmeyle "
            "ilgisiz kişisel giderler ve cezalar kanunen kabul edilmeyen gider "
            "sayılır ve matraha geri eklenir. Giderleri kategori bazında takip "
            "etmek, hem hangi kalemin büyüdüğünü görmenizi hem de beyan sırasında "
            "indirilebilir tutarı doğru hesaplamanızı sağlar."
        ),
    ),
    Doc(
        id="e-fatura",
        title="e-Fatura ve e-Arşiv",
        tags=("e-fatura", "e-arşiv", "gib", "fatura"),
        text=(
            "e-Fatura, GİB sistemine kayıtlı mükellefler arasında elektronik "
            "olarak düzenlenen faturadır; alıcı e-Fatura mükellefi değilse "
            "e-Arşiv fatura düzenlenir. Belirlenen ciro eşiğini aşan işletmeler "
            "için e-Fatura zorunludur. Faturaların dijital saklanması yasal "
            "saklama süresi boyunca geçerlidir ve kâğıt nüsha gerektirmez."
        ),
    ),
    Doc(
        id="gecikme-zammi",
        title="Vergi cezaları ve gecikme zammı",
        tags=("ceza", "gecikme", "zam", "usulsüzlük", "geç ödeme"),
        text=(
            "Vergiyi vadesinde ödememek gecikme zammı doğurur; zam aylık olarak "
            "işler ve ödenene kadar birikir. Beyannameyi hiç vermemek veya geç "
            "vermek ayrıca usulsüzlük cezası gerektirir. Nakit sıkışıklığında "
            "beyannameyi yine de zamanında verip ödemeyi tecil/taksitlendirme "
            "talebiyle yapılandırmak, hiç beyan etmemekten belirgin şekilde "
            "daha ucuzdur."
        ),
    ),
    Doc(
        id="amortisman",
        title="Amortisman",
        tags=("amortisman", "demirbaş", "sabit kıymet", "yatırım"),
        text=(
            "Bir yıldan uzun süre kullanılacak duran varlıklar doğrudan gider "
            "yazılmaz; faydalı ömürleri boyunca amortisman yoluyla itfa edilir. "
            "Bu, alım yılında tüm tutarı gider yazamayacağınız, ancak sonraki "
            "yıllarda da matrahınızı düşürmeye devam edeceğiniz anlamına gelir. "
            "Belirlenen tutarın altındaki demirbaşlar doğrudan gider yazılabilir."
        ),
    ),
    Doc(
        id="muhai-skoru",
        title="Muhai Skoru nedir",
        tags=("muhai skoru", "skor", "puan", "finansal sağlık"),
        text=(
            "Muhai Skoru, işletmenizin finansal sağlığını 0–100 arasında "
            "özetleyen bileşik bir göstergedir. Nakit tamponu, kârlılık, "
            "tahsilat performansı, vergi uyumu, gider disiplini, stok sağlığı, "
            "gelir istikrarı ve büyüme gibi ağırlıklı kategorilerden hesaplanır. "
            "Her kategori tek tek görülebildiği için skor açıklanabilirdir: "
            "düşüşün hangi kalemden geldiğini doğrudan okuyabilirsiniz."
        ),
    ),
)


DOCS_BY_ID: dict[str, Doc] = {d.id: d for d in DOCS}
