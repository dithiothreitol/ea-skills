# BRAND — tokeny wizualne karuzeli

> Wartości przepisane z `archxs-website/src/app/[locale]/globals.css` (system
> „Engineering Blueprint"). **Nie wymyślaj kolorów.** Jeśli czegoś brakuje, weź to
> z tamtego pliku albo nie używaj.

Kierunek jest tam zadeklarowany wprost: świadome odwrócenie wyglądu stron generowanych
w 2026 roku. Papier zamiast granatowo-fioletowego gradientu, szeryf plus mono zamiast
Intera wszędzie, kreska kreślarska zamiast glassmorfizmu, jeden akcent używany
oszczędnie. Karuzela idzie w całości w drugim, równie zamierzonym trybie tamtego
systemu: **blueprint at night**.

## 1. Paleta

Karuzela używa wyłącznie trybu ciemnego (klasa `.night` na każdym slajdzie).
Wartości jasne zostawione w pliku jako baza kaskady i punkt wyjścia dla ewentualnej
wersji na papier.

| Rola | Ciemny (używany) | Jasny (baza) |
|---|---|---|
| Tło arkusza | `#0e1b2c` | `#f7f5f0` |
| Karta, blok kodu | `#13253a` | `#fffdf8` |
| Tekst główny | `#e6edf4` | `#1a1c1e` |
| Tekst miękki | `#a6bacb` | `#55595d` |
| **Akcent (redline)** | `#ff7f52` | `#c8431f` |
| Drugi ton (steel) | `#7ea9c9` | `#46647f` |
| Obrys | `rgba(230,237,244,.16)` | `rgba(26,28,30,.14)` |
| Siatka / linia główna | `rgba(126,169,201,.09)` / `.16` | `rgba(26,28,30,.055)` / `.1` |

**Jeden akcent na slajd.** Redline oznacza to, co czytelnik ma zapamiętać: fragment
nagłówka, kod błędu, strefę zatwierdzoną, liczbę. Steel jest tonem konstrukcyjnym
(etykiety, obrysy kart, klucze YAML) i nigdy nie konkuruje o uwagę. Trzeciego koloru
nie ma i nie należy go dodawać.

## 2. Typografia

| Zastosowanie | Krój | Uwagi |
|---|---|---|
| Nagłówki | **Fraunces** 600 | `font-variation-settings: "SOFT" 0, "WONK" 0`, `letter-spacing: -0.018em` |
| Treść | **Inter** 400/500 | `text-wrap: pretty`, maks. szerokość 860 px |
| Liczby, kod, etykiety | **IBM Plex Mono** 400/500 | wersaliki i `letter-spacing: .18em` dla etykiety arkusza |

**Wszystkie liczby idą w mono.** Fonty leżą w `fonts/` jako woff2 (podzbiory `latin`
i `latin-ext`, bo bez `latin-ext` nie ma polskich znaków). Wszystkie trzy są na licencji
SIL Open Font License 1.1, więc wolno je dołączyć.

## 3. Geometria i elementy kreślarskie

- **Promień 4 px.** Kreślarsko, nie konsumencko. Zero dużych zaokrągleń.
- **Siatka milimetrowa** 12 px z linią główną co 96 px, wygaszona maską radialną
  (w oryginale 8/64 px; przeskalowana, bo przy 1080 px szerokości gęstsza siatka zbija
  się w szum przy zmniejszeniu do miniatury).
- **Ziarno papieru**: szum SVG przy 3,5% krycia. Zabija czytanie tła jako płaskiego
  gradientu, co jest najczęstszym sygnałem grafiki generowanej.
- **Znaczniki pasowania** w czterech rogach zamiast neonowych nawiasów.
- **Linia wymiarowa** z zakończeniami nad stopką.

## 4. Zasady treści

- Slajd **1080 × 1350 px** (4:5), margines bezpieczny 88 px, render `@2x`.
- Maks. **~30 słów na slajd**, jedna myśl na slajd.
- Najmniejszy tekst **22 px** przy 1080 px szerokości, czyli czytelny na telefonie.
- **Bez długich myślników** w treści slajdów i w treści wpisu.
- Tekst renderowany z HTML, nigdy wypalany w grafice. Literówka kosztuje edycję
  `slides.html` i ponowny render, a nie nową grafikę.
- Każda liczba i każdy kod reguły ma wpis w [`FAKTY.md`](FAKTY.md).
