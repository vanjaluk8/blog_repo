# KONAČNA VERZIJA — kako vrtiti skriptu

**Datoteka:** `output/shnl_probe_full.py`

## Što skripta radi

1. Nađe IP adresu domene.
2. Pokuša dohvatiti provider, državu i ASN preko IP API-ja / whois fallbacka.
3. Mjeri curl mrežne metrike:
   - `response_code`, `effective_url`
   - `remote_ip`, `remote_port`
   - `num_redirects`, `num_connects`
   - `size_download`, `size_header`, `size_request`, `speed_download`
   - `time_namelookup`, `time_connect`, `time_appconnect`, `time_pretransfer`, `time_starttransfer`, `time_total`
   - izvedene metrike: `dns`, `tcp_handshake`, `tls_handshake`, `ttfb_after_connect`, `download_time`
4. Pokreće Lighthouse i mjeri browser/lab metrike:
   - performance score
   - FCP, LCP, Speed Index, TBT, CLS, TTI
   - server response time, total byte weight, DOM size
   - render blocking resources, unused JS/CSS, main-thread rad, bootup time
5. Opcionalno poziva PageSpeed Insights API za field data / CrUX ako imaš API ključ:
   - field LCP p75
   - field CLS p75
   - field INP p75
   - field FCP p75
   - field TTFB p75
   - origin-level LCP/CLS/INP

## 1. Preduvjeti

Trebaš imati:

- Python 3
- `requests` paket
- `curl`
- `whois`
- Lighthouse CLI
- Chrome ili Chromium

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install -y python3 python3-pip curl whois chromium-browser npm
pip install requests
sudo npm install -g lighthouse
```

Ako je na tvojoj distribuciji paket `chromium` umjesto `chromium-browser`:

```bash
sudo apt install -y chromium
```

**Provjera:**

```bash
python3 --version
curl --version
whois --version
lighthouse --version
```

## 2. Osnovno pokretanje

Pokreni iz direktorija gdje je skripta:

```bash
python3 output/shnl_probe_full.py
```

To će napraviti CSV ovdje: `output/shnl_full_metrics.csv`

## 3. Odabir izlazne datoteke

```bash
python3 output/shnl_probe_full.py --out output/moj_rezultat.csv
```

## 4. Lighthouse preset

Desktop preset:

```bash
python3 output/shnl_probe_full.py --preset desktop
```

Perf preset:

```bash
python3 output/shnl_probe_full.py --preset perf
```

## 5. PageSpeed / CrUX field data (opcionalno)

Ako želiš i real-user / field podatke preko Google PageSpeed Insights API-ja, napravi API ključ i postavi ga u env varijablu:

```bash
export PSI_API_KEY='tvoj_api_kljuc'
```

Zatim pokreni:

```bash
python3 output/shnl_probe_full.py --psi-mobile
```

Ili za oba:

```bash
python3 output/shnl_probe_full.py --psi-mobile --psi-desktop
```

Možeš i direktno preko argumenta:

```bash
python3 output/shnl_probe_full.py --psi-api-key 'tvoj_api_kljuc' --psi-mobile
```

**Napomena:**
- Ako nemaš API ključ, PSI kolone se mogu preskočiti.
- Ako neka domena nema dovoljno CrUX podataka, neka field/origin polja mogu ostati prazna.

## 6. Preporučeni način korištenja

Najbolja praksa je napraviti dva runa:

**A) Bez PSI, za lokalni tehnički benchmark:**

```bash
python3 output/shnl_probe_full.py --preset desktop --out output/shnl_local_benchmark.csv
```

**B) S PSI mobile, za real user / field signal:**

```bash
export PSI_API_KEY='tvoj_api_kljuc'
python3 output/shnl_probe_full.py --preset desktop --psi-mobile --out output/shnl_with_field_data.csv
```

## 7. Kako čitati rezultate

**Najvažnije mrežne metrike:**

| Metrika | Opis |
|---|---|
| `curl_dns_s` | DNS lookup vrijeme |
| `curl_tcp_handshake_s` | TCP connect faza |
| `curl_tls_handshake_s` | TLS handshake |
| `curl_ttfb_after_connect_s` | Vrijeme do prvog bytea nakon uspostave veze |
| `curl_download_time_s` | Vrijeme skidanja payload-a |

**Najvažnije browser/lab metrike:**

| Metrika | Opis |
|---|---|
| `lh_fcp_ms` | Prvo nešto vidljivo |
| `lh_lcp_ms` | Najveći glavni element učitan |
| `lh_tbt_ms` | Blokiranje main threada |
| `lh_cls` | Vizualni pomaci layouta |
| `lh_tti_ms` | Kad stranica postane interaktivna |

**Najvažnije field metrike:**

- `psi_mobile_field_lcp_p75_ms`
- `psi_mobile_field_cls_p75`
- `psi_mobile_field_inp_p75_ms`

## 8. Tumačenje praktično

| Situacija | Vjerojatni uzrok |
|---|---|
| curl dobar, Lighthouse loš | Frontend problem — render-blocking resursi, JS ili veliki DOM |
| curl loš i Lighthouse loš | Hosting, backend, CDN ili mrežni sloj |
| lab dobar, field loš | Stvarni korisnici imaju lošije uređaje, mobilne mreže ili drugačiji geografski put |

## 9. Primjeri

Minimalno:

```bash
python3 output/shnl_probe_full.py
```

S drugim izlazom:

```bash
python3 output/shnl_probe_full.py --out output/final.csv
```

S Lighthouse + PSI mobile:

```bash
export PSI_API_KEY='tvoj_api_kljuc'
python3 output/shnl_probe_full.py --preset desktop --psi-mobile --out output/final_with_psi.csv
```

S oba PSI moda:

```bash
python3 output/shnl_probe_full.py --psi-mobile --psi-desktop
```
