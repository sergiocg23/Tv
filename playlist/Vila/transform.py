import json

with open("iptv.w3u", "r", encoding="utf-8") as f:
    data = json.load(f)

m3u_lines = ["#EXTM3U"]

for group in data.get("groups", []):
    group_name = group.get("name", "")
    for station in group.get("stations", []):
        name = station.get("name", "Sin nombre")
        url = station.get("url", "")
        logo = station.get("image", "")

        m3u_lines.append(
            f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group_name}", {name}'
        )
        m3u_lines.append(url)

with open("iptv.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

print("✅ Lista convertida a lista.m3u")
