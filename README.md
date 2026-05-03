KONAČNA VERZIJA — kako vrtiti skriptu

Datoteka:
- output/shnl_probe_full.py

Što skripta radi
1. Nađe IP adresu domene.
2. Pokuša dohvatiti provider, državu i ASN preko IP API-ja / whois fallbacka.
3. Mjeri curl mrežne metrike:
   - response_code, effective_url
   - remote_ip, remote_port
   - num_redirects, num_connects
   - size_download, size_header, size_request, speed_download
   - time_namelookup, time_connect, time_appconnect, time_pretransfer, time_starttransfer, time_total
   - izvedene metrike: dns, tcp_handshake, tls_handshake, ttfb_after_connect, download_time
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

--------------------------------------------------
1. PREDUVJETI
--------------------------------------------------
Trebaš imati:
- Python 3
- requests paket
- curl
- whois
- Lighthouse CLI
- Chrome ili Chromium

Primjeri instalacije:

Ubuntu/Debian:
sudo apt update
sudo apt install -y python3 python3-pip curl whois chromium-browser npm
pip install requests
sudo npm install -g lighthouse

Ako je na tvojoj distribuciji paket chromium umjesto chromium-browser:
sudo apt install -y chromium

Provjera:
python3 --version
curl --version
whois --version
lighthouse --version

--------------------------------------------------
2. OSNOVNO POKRETANJE
--------------------------------------------------
Pokreni iz direktorija gdje je skripta:

python3 output/shnl_probe_full.py

To će napraviti CSV ovdje:
output/shnl_full_metrics.csv

--------------------------------------------------
3. ODABIR IZLAZNE DATOTEKE
--------------------------------------------------
python3 output/shnl_probe_full.py --out output/moj_rezultat.csv

--------------------------------------------------
4. LIGHTHOUSE PRESET
--------------------------------------------------
Desktop preset:
python3 output/shnl_probe_full.py --preset desktop

Perf preset:
python3 output/shnl_probe_full.py --preset perf

--------------------------------------------------
5. PAGEPEED / CRUX FIELD DATA (opcionalno)
--------------------------------------------------
Ako želiš i real-user / field podatke preko Google PageSpeed Insights API-ja,
napravi API ključ i postavi ga u env varijablu:

export PSI_API_KEY='tvoj_api_kljuc'

Zatim pokreni:
python3 output/shnl_probe_full.py --psi-mobile

Ili za oba:
python3 output/shnl_probe_full.py --psi-mobile --psi-desktop

Možeš i direktno preko argumenta:
python3 output/shnl_probe_full.py --psi-api-key 'tvoj_api_kljuc' --psi-mobile

Napomena:
- Ako nemaš API ključ, PSI kolone se mogu preskočiti.
- Ako neka domena nema dovoljno CrUX podataka, neka field/origin polja mogu ostati prazna.

--------------------------------------------------
6. PREPORUČENI NAČIN KORIŠTENJA
--------------------------------------------------
Najbolja praksa je napraviti dva runa:

A) Bez PSI, za lokalni tehnički benchmark:
python3 output/shnl_probe_full.py --preset desktop --out output/shnl_local_benchmark.csv

B) S PSI mobile, za real user / field signal:
export PSI_API_KEY='tvoj_api_kljuc'
python3 output/shnl_probe_full.py --preset desktop --psi-mobile --out output/shnl_with_field_data.csv

--------------------------------------------------
7. KAKO ČITATI REZULTATE
--------------------------------------------------
Najvažnije mrežne metrike:
- curl_dns_s: DNS lookup vrijeme
- curl_tcp_handshake_s: TCP connect faza
- curl_tls_handshake_s: TLS handshake
- curl_ttfb_after_connect_s: vrijeme do prvog bytea nakon uspostave veze
- curl_download_time_s: vrijeme skidanja payload-a

Najvažnije browser/lab metrike:
- lh_fcp_ms: prvo nešto vidljivo
- lh_lcp_ms: najveći glavni element učitan
- lh_tbt_ms: blokiranje main threada
- lh_cls: vizualni pomaci layouta
- lh_tti_ms: kad stranica postane interaktivna

Najvažnije field metrike:
- psi_mobile_field_lcp_p75_ms
- psi_mobile_field_cls_p75
- psi_mobile_field_inp_p75_ms

--------------------------------------------------
8. TUMAČENJE PRAKTIČNO
--------------------------------------------------
Ako je curl dobar, a Lighthouse loš:
- problem je vjerojatno frontend, render-blocking resursi, JS ili veliki DOM

Ako je curl loš i Lighthouse loš:
- problem je vjerojatno hosting, backend, CDN ili mrežni sloj

Ako je lab dobar, a field loš:
- stvarni korisnici imaju lošije uređaje, mobilne mreže ili drugačiji geografski put

--------------------------------------------------
9. PRIMJERI
--------------------------------------------------
Minimalno:
python3 output/shnl_probe_full.py

S drugim izlazom:
python3 output/shnl_probe_full.py --out output/final.csv

S Lighthouse + PSI mobile:
export PSI_API_KEY='tvoj_api_kljuc'
python3 output/shnl_probe_full.py --preset desktop --psi-mobile --out output/final_with_psi.csv

S oba PSI moda:
python3 output/shnl_probe_full.py --psi-mobile --psi-desktop
