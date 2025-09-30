

## 7️⃣ Validación completa del stack

* **Nginx**: `http://localhost:8080/healthz` → `curl -f` debería devolver 200.
* **Jellyfin**: `http://localhost:8096/` → acceso a interfaz web.
* **AceStream**: `http://localhost:8621/` → interfaz web.
* **Warp**: Healthcheck ya configurado en docker-compose.

---

Test para probar warp.
curl -x "socks5h://127.0.0.1:9091" -fsSL "https://www.cloudflare.com/cdn-cgi/trace"
curl -x "http://127.0.0.1:9091" -fsSL "https://www.cloudflare.com/cdn-cgi/trace"

Los de tor no los uso en warp
Test: curl -I https://check.torproject.org/
Test tor: curl --socks5 127.0.0.1:9091 https://check.torproject.org/