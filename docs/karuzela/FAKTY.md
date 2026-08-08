# FAKTY — każda liczba i każdy kod ze slajdów, z miejscem, które je potwierdza

To repozytorium nie pozwala postawić w dokumentacji liczby, której nie sprawdza test.
Karuzela nie jest z tej zasady zwolniona: gdyby slajd mówił „146 reguł", a katalog miał
ich 150, pierwszy slajd łamałby regułę, którą reklamuje trzeci.

Sposób użycia: **przed każdą publikacją** należy przejść tę tabelę i sprawdzić kolumnę
„jak sprawdzić". Liczby zmieniają się przy wydaniach, slajdy nie zmieniają się same.
Stan tabeli: **2026-08-08**.

| Slajd | Twierdzenie | Źródło | Jak sprawdzić |
|---|---|---|---|
| 02 | ArchiMate 3.2 | `oracle/relationships.xml` deklaruje `version="3.2"` | `python -m easkills oracle-info` |
| 02 | widok wygenerowany, nie rysowany | `eval/example/docs/views/layered-overview.svg` | `python -m easkills render --root eval/example` |
| 02 | opis architektury w kształcie ISO 42010 | rodzina reguł `ISO` w `docs/RULES.md` | `python -m easkills conformance --root eval/example` |
| 03 | 11 569 dopuszczalnych par | `oracle/NOTICE.md`, wiersz `relationships.xml` | `python -m easkills oracle-info` |
| 03, 05, 06 | 146 reguł walidacji | `docs/RULES.md` (katalog jest źródłem prawdy) | `pytest tests/test_repo_docs.py -k rule_count` |
| 04 | kod `PROV003`, cytat nieodnaleziony w źródle | `docs/RULES.md`, rodzina `PROV` | `grep PROV003 docs/RULES.md` |
| 04 | fabrykowanie cytatów jako udokumentowana słabość modeli | `docs/BLUEPRINT.md` §2, przypis do badań | `grep -n "fabricate citations" README.md` |
| 06 | kod `REL001`, relacja niedozwolona przez macierz | `docs/RULES.md`, rodzina `REL` | `grep REL001 docs/RULES.md` |
| 06 | kod `DISP003`, odstępstwo wygasło i wciąż otwarte | `docs/RULES.md`, rodzina `DISP` | `python -m easkills validate-gov --root eval/example` |
| 06 | raport bajt w bajt identyczny przy tej samej dacie | testy determinizmu raportów | `pytest tests/test_reports.py` |
| 07 | `promote` jako jedyna droga do `model/approved/` | `easkills/promote.py` + testy stref | `pytest tests/test_promote.py` |
| 08 | dyspozycja TIME przy nakładających się aplikacjach | `easkills/reports.py`, `PORTFOLIO_KEYS` | `python -m easkills debt --root eval/example` |
| 08 | wycena wyłącznie stawkami organizacji | `easkills/cost.py`, `price()` zwraca `None` bez konfiguracji | `pytest tests/test_cost.py` |
| 09 | Rejestr Informacji DORA z modelu | `easkills/dora.py`, rodzina reguł `REG` | `python -m easkills dora-register --root eval/fixtures/finco --as-of 2026-08-08` |
| 09 | inwentarz systemów AI Act | `easkills/airegister.py`, rodzina reguł `AIR` | `python -m easkills ai-act-register --root eval/fixtures/aico --as-of 2026-08-08` |
| 09 | element bywa w obu zakresach naraz | `regulatoryScope` jako enum z kombinacjami (`ai-act dora`) | `pytest -k dual_scope` |
| 09 | praktyka zakazana z art. 5 jako błąd, nie wiersz | `AIR005` (severity error) | `grep AIR005 docs/RULES.md` |
| 09 | nadzór z art. 14, rola operatora z art. 3 | właściwości `aiOversight`, `aiRole` | `grep -n "aiOversight" easkills/genschema.py` |
| 09 | oba dokumenty generują, nie zaświadczają | nagłówek w generowanym dokumencie | `grep -n "HEADER_NOTICE" easkills/dora.py easkills/airegister.py` |
| 10 | luka wobec ramy jako nazwany węzeł (`ALN004`) | `docs/RULES.md`, rodzina `ALN` | `python -m easkills align --root <repo> --reference nist-csf-2.0` |
| 10 | NIST CSF 2.0 zweryfikowany wobec CSWP 29 | `references/nist-csf-2.0/NOTICE.md`, datowane 2026-08-07 | `pytest tests/test_align.py -k says_when` |
| 10 | NIST AI RMF 1.0: 4 funkcje, 19 kategorii | `references/nist-ai-rmf-1.0/model.yaml` | `grep -c "^  - id:" references/nist-ai-rmf-1.0/model.yaml` |
| 10 | KNF Rekomendacja D: 4 obszary, 22 rekomendacje | `references/knf-rek-d-2013/model.yaml` | `grep -c "^  - id:" references/knf-rek-d-2013/model.yaml` |
| 10 | dwa pakiety oznaczone `structure not yet verified` | `references/README.md`, kolumna Verification | `pytest tests/test_align.py -k verification_state` |
| 11 | 32 komendy CLI | lista podkomend parsera | `python -m easkills --help` |
| 11 | 25 umiejętności agentowych | katalog `skills/` | `pytest tests/test_repo_docs.py -k skill_count` |
| 11 | 716 testów | zbiór testów | `python -m pytest --collect-only -q` |
| 11 | licencja MIT | `LICENSE` (czysty tekst MIT) oraz `NOTICE.md` na zakres | GitHub wykrywa „MIT License" |

## Czego na slajdach świadomie nie ma

**Żadnego twierdzenia o skuteczności modelu językowego.** Harness pomiarowy istnieje
(`eval/harness/`), ale jego wyniki są względne wobec własnej linii bazowej i nie znaczą
nic bez kontekstu. Liczba typu „87% trafności" na slajdzie byłaby dokładnie tym rodzajem
liczby, przed którym broni się reszta tego repozytorium.

**Żadnego porównania z konkurencją.** Tabela porównawcza w `README.md` jest datowana i ma
comiesięczny obowiązek przeglądu, którego slajd nie utrzyma. Wersja wypalona w PNG
zestarzeje się cicho.

**Żadnej sugestii, że rejestr regulacyjny jest dowodem zgodności.** Slajd 09 mówi
„generują, a nie zaświadczają", bo dokładnie to mówi nagłówek generowanego dokumentu.
Zmiana tego zdania na slajdzie byłaby obietnicą, której narzędzie nie składa.

**Żadnego przemilczenia statusu weryfikacji pakietów.** Dwa z trzech pakietów
referencyjnych noszą etykietę `structure not yet verified` i slajd 10 to mówi wprost.
Pominięcie tej informacji zrobiłoby z draftu autorytet, czyli dokładnie tę awarię, przed
którą etykieta istnieje.
