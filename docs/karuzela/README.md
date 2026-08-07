# Karuzela LinkedIn (materiał po polsku)

Dziesięć slajdów 1080 × 1350 opisujących, czym jest ea-skills, jak się z niego korzysta
i gdzie robi różnicę. **To materiał marketingowy w języku polskim**, celowo trzymany
w repozytorium: karuzela, której każda liczba wskazuje test albo komendę, jest kolejnym
dowodem tezy tego projektu, a nie jego zanieczyszczeniem.

Nie jest częścią pakietu Pythonowego ani bramki CI. Nic w `easkills/` tego nie importuje
i żaden test tego nie uruchamia.

## Render

```bash
cd docs/karuzela
npm install        # raz: playwright 1.61.1
node render.mjs    # 10 x PNG @2x + karuzela.pdf w out/
node check.mjs     # kontrola, czy treść mieści się w slajdzie
```

`out/` nie jest commitowane. Źródła są, więc render odtwarza artefakty w kilkanaście
sekund, a repozytorium nie nosi 25 MB PNG-ów, które i tak przy każdej poprawce trzeba
wygenerować od nowa.

**LinkedIn przyjmuje oba warianty:** `karuzela.pdf` jako post dokumentowy (przewijany
w miejscu, wyższy czas zatrzymania) albo dziesięć PNG jako post wieloobrazkowy.
Domyślnie PDF.

## Dlaczego akurat tak

**Tekst żyje w HTML, nie w bitmapie.** Poprawka literówki to edycja `slides.html`
i ponowny render, bez ryzyka, że wróci inna grafika. To jedyny powód, dla którego
w ogóle warto składać slajdy kodem zamiast w edytorze graficznym.

**`check.mjs` jest tu z konkretnego powodu.** Slajd, którego treść przelewa się poza
kadr, nie wygląda na zepsuty: stopka po prostu znika poniżej krawędzi i nikt tego nie
zauważa aż do publikacji. Skrypt mierzy wysokość treści względem kadru i nazywa slajd,
który nie mieści się albo świeci pustką. Dwa przepełnienia znalazł przy pierwszym
przebiegu.

**Fonty są lokalne.** Reszta tego repozytorium ma zawendorowany nawet `xml.xsd`, żeby
walidacja działała bez sieci. Pobieranie kroju z Google Fonts w trakcie renderu psułoby
odtwarzalność dokładnie tam, gdzie łatwo tego nie zauważyć: pierwszy przebieg łapie
krój zastępczy i slajdy wychodzą inne niż drugi raz.

## Pliki

| Plik | Rola |
|---|---|
| [`slides.html`](slides.html) | wszystkie dziesięć slajdów, style w jednym miejscu |
| [`render.mjs`](render.mjs) | Playwright: PNG-i i PDF |
| [`check.mjs`](check.mjs) | kontrola mieszczenia się treści w kadrze |
| [`BRAND.md`](BRAND.md) | tokeny wizualne przepisane z systemu ArchXS |
| [`FAKTY.md`](FAKTY.md) | każda liczba i każdy kod reguły ze slajdów, z miejscem potwierdzenia |
| `fonts/` | Fraunces, Inter, IBM Plex Mono (woff2, OFL 1.1) |

Slajd 09 osadza `eval/example/docs/views/layered-overview.svg`, czyli realne wyjście
komendy `render`, a nie makietę. Jeśli model przykładowy się zmieni, slajd zmieni się
razem z nim przy następnym renderze.
