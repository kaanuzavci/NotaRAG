"""Akışın yeniden çalıştırılması havuzu silmemeli (2026-10-05'te bulunan hata: run() dosyanın üzerine yazıyordu;
gece qwen ile üretilen sorular, Gemini açılınca yeniden çalıştırmada kaybolacaktı). Çalıştırma: python -m tests.test_pipeline"""

from src.pipeline import merge_existing
from src.review_store import question_id


def _q(text: str, chunk: str = "D:p1", model: str = "qwen") -> dict:
    return {"model": model, "q": {"question": text}, "chunk_ids": [chunk],
            "check": {"status": "passed_checks", "rejected": []}, "verification": {"label": "verified"}}


def test_all() -> None:
    chunks = {"D:p1": {}, "D:p2": {}}
    old = [_q("Moore Yasası neyi öngörür?"), _q("CPI neyi ölçer?", "D:p2"), _q("Eski sayfadaki soru?", "D:p9")]
    items = [_q("Moore Yasası neyi öngörür?"),                 # önbellekten aynen geldi → atlanır
             _q("Moore Yasası neyi öngörür?", model="gemini"),  # başka modelden aynı metin → tekrar, reddedilir
             _q("Amdahl Yasası hızlanmayı nasıl sınırlar?", model="gemini")]
    kept, stale, new = merge_existing(old, items, chunks)
    assert [question_id(i) for i in kept] == [question_id(i) for i in old[:2]]  # eskiler korunur, değişmez
    assert len(stale) == 1 and stale[0]["chunk_ids"] == ["D:p9"]              # parçası kalmayan düşer
    assert len(new) == 2 and new[0]["check"]["rejected"] == ["duplicate"]     # tekrar doğrulamaya gitmez
    assert new[1]["check"]["status"] == "passed_checks"
    assert all(i["check"]["status"] == "passed_checks" for i in kept)


if __name__ == "__main__":
    test_all()
    print("pipeline: tüm testler geçti")
