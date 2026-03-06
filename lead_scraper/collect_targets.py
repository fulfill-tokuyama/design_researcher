"""
Serper API で関西不動産会社のターゲットURLを自動収集し targets.json を生成する
"""

import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
if not SERPER_API_KEY:
    print("SERPER_API_KEY が設定されていません")
    sys.exit(1)

SERPER_URL = "https://google.serper.dev/search"

# 関西不動産系の検索クエリ
QUERIES = [
    # 大阪
    "大阪市 不動産会社 売買仲介 地元",
    "大阪 中小 不動産会社 マンション売買",
    "堺市 不動産会社 戸建て 売買",
    "大阪 北摂 不動産屋 地域密着",
    "大阪 東大阪 不動産会社",
    # 兵庫
    "神戸市 不動産会社 売買 地域密着",
    "西宮 芦屋 不動産会社",
    "姫路 不動産会社 売買",
    # 京都
    "京都市 不動産会社 売買 地元",
    "京都 宇治 不動産会社",
    # 奈良・滋賀・和歌山
    "奈良市 不動産会社 売買",
    "滋賀 大津 不動産会社",
    "和歌山 不動産会社",
]

def search_serper(query: str, num: int = 10) -> list[dict]:
    resp = requests.post(
        SERPER_URL,
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "gl": "jp", "hl": "ja", "num": num},
    )
    resp.raise_for_status()
    return resp.json().get("organic", [])


def is_company_site(url: str) -> bool:
    """ポータルサイトや大手サイトを除外"""
    exclude = [
        # ポータル・メディア
        "suumo", "homes.co.jp", "athome", "yahoo", "google",
        "wikipedia", "youtube", "twitter", "facebook", "instagram",
        "rakuten", "price.co.jp", "nikkei.com", "navitime.co.jp",
        "house.goo.ne.jp", "baseconnect.in", "ieuri.com",
        "home4u.jp", "hatomarksite", "lifullhomes", "sumai-step.com",
        "iimon.co.jp", "smilease.jp", "leadcreation.co.jp",
        "fkr.or.jp", "saleofreal-estateguide",
        # 大手・協会
        "realestate.co.jp", "fudousan.or.jp", "zentaku.or.jp",
        "chintai", "door.ac", "sumitomo", "mitsui-chintai",
        "tokyu-livable", "openhouse", "haseko", "daiwa",
        "century21", "era-japan", "housedo", "katitas",
        "rehouse", "nomu.com", "osaka-takken.or.jp",
        # 賃貸ポータル
        "homemate.co.jp", "sumo-t-",
    ]
    url_lower = url.lower()
    return not any(ex in url_lower for ex in exclude)


def extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc


def main():
    all_urls = {}  # domain -> {url, title, query}

    for query in QUERIES:
        print(f"[search] {query}")
        try:
            results = search_serper(query)
        except Exception as e:
            print(f"  error: {e}")
            continue

        for r in results:
            url = r.get("link", "")
            title = r.get("title", "")
            if not url or not is_company_site(url):
                continue

            domain = extract_domain(url)
            if domain not in all_urls:
                # トップページに正規化
                from urllib.parse import urlparse
                parsed = urlparse(url)
                top_url = f"{parsed.scheme}://{parsed.netloc}/"
                all_urls[domain] = {
                    "url": top_url,
                    "title": title,
                    "query": query,
                }
                print(f"  + {title[:40]} ({domain})")

        time.sleep(1)  # レート制限

    # targets.json 出力
    targets = [v["url"] for v in all_urls.values()]
    out_path = Path(__file__).resolve().parent / "targets.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)

    # 詳細情報も別ファイルに保存
    details_path = Path(__file__).resolve().parent / "targets_detail.json"
    with open(details_path, "w", encoding="utf-8") as f:
        json.dump(list(all_urls.values()), f, ensure_ascii=False, indent=2)

    print(f"\n{len(targets)} 件のターゲットURLを収集しました")
    print(f"  -> {out_path}")
    print(f"  -> {details_path}")


if __name__ == "__main__":
    main()
