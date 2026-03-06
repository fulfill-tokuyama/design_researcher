"""
Firecrawl + Gemini ベースのリードスクレイパー
Firecrawlでサイト情報をMarkdown取得 -> Geminiで企業情報を構造化抽出
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

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("google-genai が必要です: pip install google-genai")
    sys.exit(1)

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"

EXTRACT_PROMPT = """以下は日本の不動産会社のWebサイトから取得したテキストです。
この中から企業情報を抽出してJSON形式で返してください。

## 抽出対象
- company_name: 会社名（株式会社○○ の形式）
- representative: 代表者名
- address: 住所
- phone: 電話番号（代表番号）
- email: メールアドレス
- business_type: 事業内容（売買/賃貸/管理 等）
- license_number: 宅建業免許番号
- employee_count: 従業員数
- established: 設立年

情報が見つからない項目は空文字にしてください。
JSONのみを出力。バッククォートや説明文は不要。

## サイトテキスト
{text}"""


def scrape_with_firecrawl(url: str) -> tuple[str | None, list[str]]:
    """FirecrawlでサイトをMarkdownとして取得。(markdown, links)を返す"""
    try:
        resp = requests.post(
            FIRECRAWL_URL,
            headers={
                "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"url": url, "formats": ["markdown", "links"]},
            timeout=45,
        )
        if resp.status_code != 200:
            print(f"  [firecrawl] {url} -> HTTP {resp.status_code}")
            return None, []
        data = resp.json()
        if not data.get("success"):
            return None, []
        md = data.get("data", {}).get("markdown", "")
        links = data.get("data", {}).get("links", [])
        return (md[:8000] if md else None), (links or [])
    except Exception as e:
        print(f"  [firecrawl] {url} -> error: {e}")
        return None, []


def extract_company_info(text: str, gemini_client, url: str) -> dict | None:
    """GeminiでMarkdownから企業情報を構造化抽出"""
    try:
        resp = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=EXTRACT_PROMPT.format(text=text),
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=512,
            ),
        )
        result_text = resp.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            result_text = result_text.rsplit("```", 1)[0]
        info = json.loads(result_text)
        info["website"] = url
        info["source_url"] = url
        return info
    except Exception as e:
        print(f"  [gemini] extract error: {e}")
        return None


def find_company_page_url(links: list[str], base_url: str) -> str | None:
    """リンク一覧から会社概要ページのURLを特定"""
    from urllib.parse import urlparse
    base_domain = urlparse(base_url).netloc

    keywords = ["company", "about", "gaiyou", "profile", "corporate", "outline"]
    for link in links:
        if not isinstance(link, str):
            continue
        parsed = urlparse(link)
        # 同一ドメインのみ
        if parsed.netloc and parsed.netloc != base_domain:
            continue
        path_lower = parsed.path.lower()
        if any(kw in path_lower for kw in keywords):
            # 完全URLにする
            if not parsed.scheme:
                return base_url.rstrip("/") + "/" + link.lstrip("/")
            return link
    return None


def scrape_company_page(url: str, gemini_client) -> dict | None:
    """1社分のスクレイピング: Firecrawl + Gemini"""
    # トップページ取得
    md, links = scrape_with_firecrawl(url)
    if not md:
        return None

    # 会社概要ページをリンクから探して追加取得
    company_url = find_company_page_url(links, url)
    if company_url:
        print(f"  [company] {company_url}")
        company_md, _ = scrape_with_firecrawl(company_url)
        if company_md and len(company_md) > 200:
            md = md + "\n\n--- 会社概要ページ ---\n\n" + company_md[:5000]

    info = extract_company_info(md, gemini_client, url)
    return info


def run(targets_path: str, output_path: str = None):
    """ターゲットURLリストからリード情報を収集"""
    if not FIRECRAWL_API_KEY:
        print("FIRECRAWL_API_KEY が設定されていません")
        return []
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY が設定されていません")
        return []

    with open(targets_path, encoding="utf-8") as f:
        urls = json.load(f)

    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    leads = []

    print(f"Firecrawl + Gemini でリード収集開始 ({len(urls)} 件)")
    print("=" * 60)

    for i, url in enumerate(urls):
        print(f"[{i+1}/{len(urls)}] {url}")
        info = scrape_company_page(url, gemini_client)

        if info and info.get("company_name"):
            leads.append(info)
            name = info.get("company_name", "")
            phone = info.get("phone", "")
            email = info.get("email", "")
            print(f"  -> {name} | {phone} | {email}")
        else:
            print(f"  -> (抽出失敗)")

        time.sleep(1)  # レート制限

    print("=" * 60)
    print(f"収集完了: {len(leads)}/{len(urls)} 件")

    # 保存
    if not output_path:
        output_path = str(Path(__file__).resolve().parent / "leads_firecrawl.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)
    print(f"保存: {output_path}")

    return leads


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", "-t", default="targets.json")
    parser.add_argument("--output", "-o", default=None)
    args = parser.parse_args()
    run(args.targets, args.output)
