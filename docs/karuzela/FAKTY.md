# FAKTY — każda liczba i każdy kod ze slajdów, z miejscem, które je potwierdza

To repozytorium nie pozwala postawić w dokumentacji liczby, której nie sprawdza test.
Karuzela nie jest z tej zasady zwolniona: gdyby slajd mówił „141 reguł", a katalog miał
ich 143, pierwszy slajd łamałby regułę, którą reklamuje trzeci.

Sposób użycia: **przed każdą publikacją** przejdź tę tabelę i sprawdź kolumnę „jak
sprawdzić". Liczby zmieniają się przy wydaniach, slajdy nie zmieniają się same.

| Slajd | Twierdzenie | Źródło | Jak sprawdzić |
|---|---|---|---|
| 02 | ArchiMate 3.2 | `oracle/relationships.xml` deklaruje `version="3.2"` | `python -m easkills oracle-info` |
| 02 | opis architektury w kształcie ISO 42010 | rodzina reguł `ISO` w `docs/RULES.md` | `python -m easkills conformance --root eval/example` |
| 03 | 11 569 dopuszczalnych par | `oracle/NOTICE.md`, wiersz `relationships.xml` | `python -m easkills oracle-info` |
| 03, 06 | 141 reguł walidacji | `docs/RULES.md` (katalog jest źródłem prawdy) | `pytest tests/test_repo_docs.py -k rule_count` |
| 04 | kod `PROV003`, cytat nieodnaleziony w źródle | `docs/RULES.md`, rodzina `PROV` | `grep PROV003 docs/RULES.md` |
| 04 | „citation that cannot be located is a fabricated citation" | cytat dosłowny z opisu `PROV003` | jw. |
| 06 | kod `REL001`, relacja niedozwolona przez macierz | `docs/RULES.md`, rodzina `REL` | `grep REL001 docs/RULES.md` |
| 06 | kod `DISP003`, odstępstwo wygasło i wciąż otwarte | `docs/RULES.md`, rodzina `DISP` | `python -m easkills validate-gov --root eval/example` |
| 06 | raport bajt w bajt taki sam przy tej samej dacie | testy determinizmu raportów | `pytest tests/test_reports.py` |
| 07 | `promote` jako jedyna droga do `model/approved/` | `easkills/promote.py` + testy stref | `pytest tests/test_promote.py` |
| 09 | widok wygenerowany, nie rysowany | `eval/example/docs/views/layered-overview.svg` | `python -m easkills render --root eval/example` |
| 09 | Rejestr Informacji DORA z modelu | `easkills/dora.py`, rodzina reguł `REG` | `python -m easkills dora-register --root eval/fixtures/finco --as-of 2026-08-07` |
| 09 | luki wobec NIST CSF 2.0 co do węzła | `references/nist-csf-2.0/`, kod `ALN004` | `python -m easkills align --root <repo> --reference nist-csf-2.0` |
| 09 | dyspozycja TIME przy nakładających się aplikacjach | `easkills/reports.py`, `PORTFOLIO_KEYS` | `python -m easkills debt --root eval/example` |
| 10 | 31 komend CLI | lista podkomend parsera | `python -m easkills --help` |
| 10 | 684 testy | zbiór testów | `python -m pytest --collect-only -q` |
| 10 | licencja MIT | `LICENSE` (czysty tekst MIT) oraz `NOTICE.md` na zakres | GitHub wykrywa „MIT License" |

## Czego na slajdach świadomie nie ma

**Liczby 24 umiejętności.** Mieściła się, ale nic nie wnosi dla odbiorcy spoza projektu:
umiejętność agenta to plik z instrukcją, a nie funkcja, którą da się porównać.

**Żadnego twierdzenia o skuteczności modelu językowego.** Harness pomiarowy istnieje
(`eval/harness/`), ale jego wyniki są względne wobec własnej linii bazowej i nie znaczą
nic bez kontekstu. Liczba typu „87% trafności" na slajdzie byłaby dokładnie tym rodzajem
liczby, przed którym broni się reszta tego repozytorium.

**Żadnego porównania z konkurencją.** Tabela porównawcza w `README.md` jest datowana i ma
comiesięczny obowiązek przeglądu, którego slajd nie utrzyma. Wersja wypalona w PNG
zestarzeje się cicho.
