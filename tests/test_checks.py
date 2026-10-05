"""Kod kontrolü testleri (pilotta bulunan durumlar). Çalıştırma: python -m tests.test_checks"""

from src.generation.schema import Question
from src.verification.checks import _CONTEXT_REF, _DEMONSTRATIVE_START, check, mark_duplicates

CTX = [{"page": 16, "text": "Bireyler rölatif uygunluk değerlerine göre seçilir.\nBaşlıca dezavantajı sadece tüm domaini "
        "pozitif değerli olan maksimizasyon problemlerine uygulanabilmesidir."},
       {"page": 11, "text": "Hedef $\longrightarrow$ maksimizasyon $x \in [0, 30]$"}]


def _ref(s: str) -> bool:
    return bool(_CONTEXT_REF.search(s) or _DEMONSTRATIVE_START.search(s))


def test_all() -> None:
    # metne atıf: pilotta gpt-oss ve qwen'den kaçanlar
    assert _ref("Bu seçim stratejisinin temel dezavantajı nedir?")
    assert _ref("Verilen genetik algoritma çözüm örneğinde x aralığı nedir?")
    assert _ref("Genetik algoritmanın aşağıdaki avantajlarından hangisi metinde belirtilmiştir?")
    assert not _ref("Bu nedenle genetik algoritmalar neden tercih edilir?")
    # EN→TR pilotunda kaçan: öğrenci değerleri görmüyor
    assert _ref("Verilen uyumluluk (fitness) değerlerine göre 2 numaralı kromozomun sırası kaçtır?")
    assert not _ref("Optimizasyonda verilen kısıtlar ne işe yarar?")
    # D/Y cevabı çıktı dilinde gelebilir
    assert Question(question="GA yalnızca sürekli parametreleri optimize edebilir.", type="true_false",
                    answer="Yanlış", evidence_quote="x" * 5).answer == "false"
    # cevap-şık iki yönlü içerme ('Üç farklı grup' ↔ 'Üç') ve LaTeX'li kanıt
    q = Question(question="Rulet tekerleği seçiminde x hangi aralıkta?", type="multiple_choice",
                 options=["Dört", "Beş", "İki", "Üç"], answer_index=3, answer="Üç farklı grup",
                 evidence_quote="Hedef → maksimizasyon x ∈ [0, 30]")
    r = check(q, CTX)
    assert "answer_option_mismatch" not in r["rejected"] and r["evidence_match"] == "exact" and r["evidence_page"] == 11
    # metinde olmayan kanıt reddedilir
    bad = q.model_copy(update={"evidence_quote": "rulet tekerleği her zaman en iyisidir"})
    assert "evidence_not_found" in check(bad, CTX)["rejected"]
    # duyarlılık testindeki 'iki doğru şık' bozulması kodda da yakalanmalı
    dup = q.model_copy(update={"options": ["Dört", "Başka bir deyişle: Üç", "İki", "Üç"]})
    assert "near_duplicate_options" in check(dup, CTX)["rejected"]
    # ...ama yalnızca sayısı farklı şıklar tekrar sayılmaz (pilotun en iyi 'uygulama' sorusu buna takılmıştı)
    num = q.model_copy(update={"options": ["ρ sayısı 0.25'ten büyük olmalıdır.", "ρ sayısı tam olarak 0.25'e eşit olmalıdır.",
                                           "ρ sayısı 0.75'ten büyük olmalıdır.", "ρ sayısı 0.25'ten küçük olmalıdır."],
                               "answer_index": 3, "answer": "ρ sayısı 0.25'ten küçük olmalıdır."})
    assert "near_duplicate_options" not in check(num, CTX)["rejected"]
    # ...ve aynı kelimelerin farklı sırası da tekrar değil (EN→TR pilotunda iki yanlış alarm)
    order = q.model_copy(update={"options": ["Çaprazlama, Mutasyon, Bitiş", "Seçim, Mutasyon, Çaprazlama",
                                             "Başlatma, Değerlendirme, Seçim", "Seçim, Çaprazlama, Mutasyon"],
                                 "answer_index": 3, "answer": "Seçim, Çaprazlama, Mutasyon"})
    assert "near_duplicate_options" not in check(order, CTX)["rejected"]
    # Gemini cevap alanına açıklamalı cümle yazıyor → red değil (bilişsel düzey deneyinde 12 boşuna red)
    expl = q.model_copy(update={"options": ["%0.1-%6'sı", "%10-%20'si", "%50'si", "%90'ı"], "answer_index": 0,
                                "answer": "Kullanılan pestisitlerin sadece %0.1 ile %6'sı hedef canlıya ulaşır."})
    assert "answer_option_mismatch" not in check(expl, CTX)["rejected"]
    # ...ama cevap metni anahtardan başka bir şıkkı anlatıyorsa gerçek hata
    wrong = expl.model_copy(update={"answer": "Pestisitlerin yarısı, yani %50'si hedef canlıya ulaşır."})
    assert "answer_option_mismatch" in check(wrong, CTX)["rejected"]
    # D/Y cevabı açıklamalı: ilk kelime belirleyici
    tf = Question(question="Organik tarım her zaman verimi düşürür.", type="true_false",
                  answer="Yanlış. Metne göre bu genelleme doğru değildir.", evidence_quote="x" * 5)
    assert tf.answer == "false"
    # kesin ifadeli çeldiriciler (yalnızca-şıklar testinde cevabı ele veren desen)
    absq = q.model_copy(update={"options": ["Sadece tek bir optimum bulabilmesi", "Lokal optimuma takılmadan arayabilmesi",
                                            "Türev bilgisinin zorunlu olması", "Yalnızca ayrık parametrelerle çalışması"],
                                "answer_index": 1, "answer": "Lokal optimuma takılmadan arayabilmesi"})
    assert "absolute_distractors" in check(absq, CTX)["flags"]
    # yeniden çalıştırma: havuzdaki sorunun tekrarı reddedilir, havuzdaki soruya dokunulmaz (pipeline/request eklemesi)
    pool = [{"q": {"question": "Rulet tekerleği seçiminin başlıca dezavantajı nedir?"},
             "check": {"status": "passed_checks", "rejected": []}}]
    new = [{"q": {"question": "Rulet tekerleği seçiminin başlıca dezavantajı nedir?"},
            "check": {"status": "passed_checks", "rejected": []}},
           {"q": {"question": "Turnuva seçiminde turnuva büyüklüğü neyi etkiler?"},
            "check": {"status": "passed_checks", "rejected": []}}]
    mark_duplicates(new, keep=pool)
    assert new[0]["check"]["rejected"] == ["duplicate"] and new[1]["check"]["status"] == "passed_checks"
    assert pool[0]["check"]["status"] == "passed_checks"


if __name__ == "__main__":
    test_all()
    print("checks: tüm testler geçti")
