## 7️⃣ Validación completa del stack

- **Nginx**: `http://localhost:8080/healthz` → `curl -f` debería devolver 200.
- **Jellyfin**: `http://localhost:8096/` → acceso a interfaz web.
- **AceStream**: `http://localhost:8621/` → interfaz web.
- **Warp**: Healthcheck ya configurado en docker compose.

---

Test para probar warp.
curl -x "socks5h://127.0.0.1:9091" -fsSL "https://www.cloudflare.com/cdn-cgi/trace"
curl -x "http://127.0.0.1:9091" -fsSL "https://www.cloudflare.com/cdn-cgi/trace"

Para probarlo desde otro contenedor.
curl -x "socks5h://warp" -fsSL "https://www.cloudflare.com/cdn-cgi/trace"
curl -x "http://warp:9091" -fsSL "https://www.cloudflare.com/cdn-cgi/trace"

Los de tor no los uso en warp
Test: curl -I https://check.torproject.org/
Test tor: curl --socks5 127.0.0.1:9091 https://check.torproject.org/



acestream y m3u
Estas dos no sirven
https://test-streams.mux.dev/
https://ottverse.com/free-hls-m3u8-test-urls/

✔️ Solución correcta para testear tu motor

La única forma 100% fiable es:

Coges un vídeo corto (10–30 s)

Lo publicas tú mismo en Ace Stream

Lo reproduces desde tu motor

Así:

sabes que el stream existe

sabes que hay seed

sabes que si falla, es tu motor