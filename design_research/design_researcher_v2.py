"""
LeadGenius AI - デザイン自動調査 v2（改良版）
=============================================

推奨アーキテクチャ:
  Gemini(KW生成) → Serper(検索) → Firecrawl(デザイン抽出) → Gemini(補足分析) → ストック

変更点 v1 → v2:
  - Google検索スクレイピング → Serper.dev API（安定・高速）
  - Gemini HTMLパース → Firecrawl Branding Format（構造化抽出）
  - Scrapling は Firecrawl失敗時のフォールバック + 詳細HTML取得用に残存
  - トレンド分析の強化（類似デザインのクラスタリング等）

環境変数:
    GEMINI_API_KEY     : Google Gemini API キー
    SERPER_API_KEY     : Serper.dev API キー（無料2,500クエリ/月）
    FIRECRAWL_API_KEY  : Firecrawl API キー（無料枠あり）

セットアップ:
    pip install "scrapling[all]" google-genai requests
    scrapling install
    python design_researcher_v2.py
"""

import json
import hashlib
import re
import os

# .env をプロジェクトルートから読み込み
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import time
import logging
import random
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import urlparse

import requests

# ─── Gemini ───
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# ─── Scrapling（フォールバック用）───
try:
    from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher
    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False

# ─── ロギング ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("design_v2")


# =============================================================================
# 設定
# =============================================================================

DEFAULT_CONFIG = {
    # ─── キーワード設定 ───
    "big_keywords": [
        "LP デザイン おしゃれ",
        "ランディングページ デザイン 最新",
        "SaaS LP デザイン",
        "BtoB サービスサイト デザイン",
        "AI サービス ランディングページ",
        "不動産 ホームページ デザイン",
        "コーポレートサイト かっこいい",
        "DX サービス LP",
    ],
    "small_keyword_count": 5,           # ビッグKWあたりのスモールKW生成数
    "daily_query_limit": 15,            # 1日の検索クエリ上限
    "search_top_n": 10,                 # 検索結果の取得件数
    "max_analysis_per_run": 30,         # 1回の分析上限

    # ─── API設定 ───
    "gemini_model": "gemini-2.0-flash",
    "serper_gl": "jp",                  # Serper: 国コード
    "serper_hl": "ja",                  # Serper: 言語
    "firecrawl_timeout": 30,

    # ─── フィルタリング ───
    "exclude_domains": [
        "pinterest.com", "youtube.com", "twitter.com", "x.com",
        "facebook.com", "instagram.com", "amazon.co.jp", "rakuten.co.jp",
        "wikipedia.org", "note.com", "qiita.com", "zenn.dev",
    ],
    "min_design_score": 50,             # ストックする最低スコア

    # ─── 出力 ───
    "output_dir": "./design_stock_v2",
}


def load_config(path: str = "config_v2.json") -> dict:
    config = DEFAULT_CONFIG.copy()
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    return config


# =============================================================================
# データモデル
# =============================================================================

@dataclass
class DesignEntry:
    id: str = ""
    url: str = ""
    domain: str = ""
    title: str = ""
    search_query: str = ""
    search_rank: int = 0
    discovered_at: str = ""

    # Firecrawl Branding Format で取得
    brand_colors: dict = field(default_factory=dict)
    brand_fonts: list = field(default_factory=list)
    brand_typography: dict = field(default_factory=dict)
    brand_spacing: dict = field(default_factory=dict)
    brand_logo: dict = field(default_factory=dict)
    brand_ui_components: list = field(default_factory=list)

    # Gemini 補足分析
    aesthetic: str = ""
    overview: str = ""
    design_score: float = 0.0
    industry: str = ""
    tags: list = field(default_factory=list)
    layout: dict = field(default_factory=dict)
    effects: dict = field(default_factory=dict)
    standout_elements: list = field(default_factory=list)
    design_principles: list = field(default_factory=list)
    reuse_tips: list = field(default_factory=list)

    # メタ
    data_source: str = ""               # "firecrawl" | "scrapling" | "both"

    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# Step 1: Gemini - スモールキーワード自動生成
# =============================================================================

KW_PROMPT = """あなたはWebデザインとSEOの専門家です。
「{big_keyword}」に対して、検索するとおしゃれなWebサイトが見つかるスモールキーワードを{count}個生成してください。

要件:
- デザインスタイル・トレンドに踏み込んだ具体的なキーワード
- 2025-2026年のトレンドを意識
- 日本語・英語混在OK
- 業界特化、スタイル特化、技術特化のバリエーション

出力: JSON配列のみ（説明不要）
例: ["SaaS LP ダークUI グラデーション", "LP ミニマル 余白 2025"]"""


class KeywordGenerator:
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, big_keyword: str, count: int = 5) -> list[str]:
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=KW_PROMPT.format(big_keyword=big_keyword, count=count),
                config=types.GenerateContentConfig(temperature=0.9, max_output_tokens=512),
            )
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            kws = json.loads(text)
            if isinstance(kws, list):
                log.info(f"  KW生成: {big_keyword} → {len(kws)}個")
                return kws
        except Exception as e:
            log.warning(f"  KW生成失敗: {e}")
        return []

    def generate_all(self, big_keywords: list[str], count_per: int = 5) -> list[dict]:
        queries = []
        for bk in big_keywords:
            for sk in self.generate(bk, count_per):
                queries.append({"big_keyword": bk, "query": sk})
            queries.append({"big_keyword": bk, "query": bk})
        return queries


# =============================================================================
# Step 2: Serper.dev - 安定した検索結果取得
# =============================================================================

class SerperSearch:
    """Serper.dev APIで検索結果を取得（無料2,500クエリ/月）"""

    API_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: str, gl: str = "jp", hl: str = "ja"):
        self.api_key = (api_key or "").strip()
        self.gl = gl
        self.hl = hl

    def search(self, query: str, num: int = 10) -> list[dict]:
        try:
            headers = {
                "x-api-key": self.api_key,  # Serper公式: x-api-key (小文字)
                "Content-Type": "application/json",
            }
            resp = requests.post(
                self.API_URL,
                headers=headers,
                json={"q": query, "gl": self.gl, "hl": self.hl, "num": num},
                timeout=10,
            )

            if resp.status_code == 403:
                log.warning(
                    f"  Serper 403 Forbidden: API_KEY先頭5文字={self.api_key[:5] if self.api_key else '(空)'}***, "
                    f"URL={self.API_URL}, レスポンス={resp.text[:200]}"
                )
                return []

            resp.raise_for_status()
            data = resp.json()

            results = []
            for i, item in enumerate(data.get("organic", [])[:num]):
                results.append({
                    "rank": i + 1,
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "domain": urlparse(item.get("link", "")).netloc,
                })

            log.info(f"  Serper: '{query}' → {len(results)}件")
            return results

        except Exception as e:
            log.warning(f"  Serper検索失敗: {query} - {e}")
            return []


# =============================================================================
# Step 3: Firecrawl - デザイン要素の構造化抽出
# =============================================================================

class FirecrawlBranding:
    """Firecrawl Branding Format APIでデザインDNAを一発抽出"""

    API_URL = "https://api.firecrawl.dev/v1/scrape"

    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = timeout

    def extract(self, url: str) -> dict:
        """URLからブランディングデータを抽出"""
        try:
            resp = requests.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "formats": ["branding", "markdown"],
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                result = data.get("data", {})
                branding = result.get("branding", {})
                markdown = result.get("markdown", "")

                log.info(f"    Firecrawl OK: {url}")
                return {
                    "success": True,
                    "branding": branding,
                    "markdown": markdown[:3000],  # トークン節約
                    "metadata": result.get("metadata", {}),
                }

            log.warning(f"    Firecrawl失敗: {url} - {data.get('error', 'unknown')}")
            return {"success": False}

        except Exception as e:
            log.warning(f"    Firecrawl例外: {url} - {e}")
            return {"success": False}


# =============================================================================
# Step 3b: Scrapling - フォールバック
# =============================================================================

class ScraplingFallback:
    """Firecrawl失敗時のフォールバック"""

    @staticmethod
    def fetch(url: str) -> dict:
        if not HAS_SCRAPLING:
            return {"success": False, "error": "scrapling not installed"}

        try:
            page = Fetcher.get(url, stealthy_headers=True, timeout=15)
            html = page.css("html").get("") or ""
            title = page.css("title::text").get("") or ""

            if len(html) < 500:
                # DynamicFetcherにフォールバック
                page = DynamicFetcher.fetch(url, headless=True, network_idle=True, timeout=20)
                html = page.css("html").get("") or ""
                title = page.css("title::text").get("") or ""

            if html:
                log.info(f"    Scrapling OK: {url} ({len(html)}文字)")
                return {"success": True, "html": html[:15000], "title": title}

        except Exception as e:
            log.warning(f"    Scrapling失敗: {url} - {e}")

        return {"success": False}


# =============================================================================
# Step 4: Gemini - 補足分析 & スコアリング
# =============================================================================

ANALYSIS_PROMPT = """あなたはエリートWebデザイナーです。以下のデザインデータを分析し、補足情報を付与してください。

## サイト情報
URL: {url}
タイトル: {title}

## Firecrawlブランディングデータ
{branding_json}

## ページ内容（概要）
{content_snippet}

以下のJSON形式のみ出力してください:
{{
    "aesthetic": "デザインスタイル名（例: 'ミニマル・プレミアム', 'ボールド・テック'）",
    "overview": "デザイン全体の印象を2-3文で",
    "design_score": 0-100の整数（独創性30% + 統一感30% + 完成度20% + トレンド性20%）,
    "industry": "業界カテゴリ",
    "tags": ["タグ1", "タグ2", "タグ3", "タグ4", "タグ5"],
    "layout": {{
        "sections": ["セクション一覧"],
        "grid_style": "レイアウト手法",
        "spacing_philosophy": "余白の使い方"
    }},
    "effects": {{
        "animations": ["アニメーション種類"],
        "hover_effects": ["ホバーエフェクト"],
        "backgrounds": "背景の処理方法"
    }},
    "standout_elements": ["特徴的なデザイン要素5つ"],
    "design_principles": ["核となるデザイン原則3-5つ"],
    "reuse_tips": ["このデザインを参考にする時のポイント3つ"]
}}"""


class GeminiAnalyzer:
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def analyze(self, url: str, title: str, branding: dict, content: str) -> dict:
        prompt = ANALYSIS_PROMPT.format(
            url=url,
            title=title,
            branding_json=json.dumps(branding, ensure_ascii=False, indent=2)[:3000],
            content_snippet=content[:2000],
        )
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=1500),
            )
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            log.warning(f"    Gemini分析失敗: {e}")
            return {}


# =============================================================================
# Step 5: ストック管理
# =============================================================================

class DesignStock:
    def __init__(self, output_dir: str):
        self.dir = Path(output_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "index.json"
        self.index = self._load()

    def _load(self) -> dict:
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"created_at": datetime.now().isoformat(), "entries": {}, "runs": []}

    def _save(self):
        self.index["total"] = len(self.index["entries"])
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def has_url(self, url: str) -> bool:
        h = hashlib.md5(url.encode()).hexdigest()[:12]
        return h in self.index["entries"]

    def add(self, entry: DesignEntry):
        self.index["entries"][entry.id] = {
            "url": entry.url, "domain": entry.domain, "aesthetic": entry.aesthetic,
            "design_score": entry.design_score, "industry": entry.industry,
            "tags": entry.tags, "discovered_at": entry.discovered_at,
        }
        detail_path = self.dir / f"{entry.id}.json"
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)
        self._save()

    def add_run(self, summary: dict):
        self.index["runs"].append(summary)
        self.index["runs"] = self.index["runs"][-90:]
        self._save()

    def get_top(self, n: int = 20) -> list[dict]:
        entries = list(self.index["entries"].values())
        entries.sort(key=lambda x: x.get("design_score", 0), reverse=True)
        return entries[:n]

    def export_trend_report(self) -> str:
        entries = list(self.index["entries"].values())
        if not entries:
            return ""

        total = len(entries)
        avg = sum(e.get("design_score", 0) for e in entries) / total

        # タグ集計
        tag_map = {}
        for e in entries:
            for t in e.get("tags", []):
                tag_map[t] = tag_map.get(t, 0) + 1
        top_tags = sorted(tag_map.items(), key=lambda x: x[1], reverse=True)[:20]

        # スタイル集計
        style_map = {}
        for e in entries:
            s = e.get("aesthetic", "不明")
            style_map[s] = style_map.get(s, 0) + 1
        top_styles = sorted(style_map.items(), key=lambda x: x[1], reverse=True)[:15]

        # 業界集計
        ind_map = {}
        for e in entries:
            ind = e.get("industry", "不明")
            ind_map[ind] = ind_map.get(ind, 0) + 1

        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {"total": total, "avg_score": round(avg, 1)},
            "trending_tags": [{"tag": t, "count": c} for t, c in top_tags],
            "trending_styles": [{"style": s, "count": c} for s, c in top_styles],
            "industries": ind_map,
            "top_10": sorted(entries, key=lambda x: x.get("design_score", 0), reverse=True)[:10],
        }

        path = self.dir / f"trend_{datetime.now().strftime('%Y%m%d')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        log.info(f"📊 トレンドレポート: {path}")
        return str(path)


# =============================================================================
# 統合パイプライン
# =============================================================================

class DesignResearchPipelineV2:
    def __init__(self, config: dict = None):
        self.cfg = config or load_config()

        # API キー取得（前後の空白を除去）
        self.gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        self.serper_key = (os.getenv("SERPER_API_KEY") or "").strip()
        self.firecrawl_key = (os.getenv("FIRECRAWL_API_KEY") or "").strip()

        # デバッグ: キーの先頭5文字をログ出力（読み込み確認用）
        if self.gemini_key:
            log.info(f"   [DEBUG] GEMINI_API_KEY 読み込みOK: 先頭5文字={self.gemini_key[:5]}***")
        else:
            log.warning("   [DEBUG] GEMINI_API_KEY が空です")
        if self.serper_key:
            log.info(f"   [DEBUG] SERPER_API_KEY 読み込みOK: 先頭5文字={self.serper_key[:5]}***")
        else:
            log.warning("   [DEBUG] SERPER_API_KEY が空です")

        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY を設定してください")

        # コンポーネント初期化
        self.kw_gen = KeywordGenerator(self.gemini_key, self.cfg["gemini_model"])
        self.searcher = SerperSearch(
            self.serper_key, gl=self.cfg["serper_gl"], hl=self.cfg["serper_hl"]
        ) if self.serper_key else None
        self.firecrawl = FirecrawlBranding(
            self.firecrawl_key, self.cfg["firecrawl_timeout"]
        ) if self.firecrawl_key else None
        self.scrapling_fb = ScraplingFallback()
        self.analyzer = GeminiAnalyzer(self.gemini_key, self.cfg["gemini_model"])
        self.stock = DesignStock(self.cfg["output_dir"])

        # スクリーンショット + 変化検知
        try:
            from design_monitor import DesignMonitor
            self.monitor = DesignMonitor(
                firecrawl_key=self.firecrawl_key,
                gemini_key=self.gemini_key,
                gemini_model=self.cfg["gemini_model"],
                stock_dir=self.cfg["output_dir"],
            )
        except ImportError:
            self.monitor = None

        # Supabase連携（オプション）
        try:
            from supabase_store import SupabaseDesignStore
            supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
            supabase_key = (os.getenv("SUPABASE_KEY") or "").strip()

            # ダミー値の場合はスキップ（エラーではなくINFO）
            def _is_dummy_supabase(url: str, key: str) -> bool:
                if not url or not key:
                    return True
                if "xxxxx" in url.lower():
                    return True
                # プレースホルダー（例: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...）
                if key.strip().endswith("..."):
                    return True
                return False

            if _is_dummy_supabase(supabase_url, supabase_key):
                log.info("   Supabase: 未設定（スキップ）")
                self.supabase = None
            elif supabase_url and supabase_key:
                self.supabase = SupabaseDesignStore(supabase_url, supabase_key, self.gemini_key)
                log.info("   Supabase: ✅")
            else:
                self.supabase = None
        except Exception as e:
            log.info(f"   Supabase: 接続スキップ ({e})")
            self.supabase = None

    def run(self):
        start = datetime.now()
        log.info("=" * 60)
        log.info("🚀 デザイン自動調査 v2 パイプライン開始")
        log.info(f"   Serper:    {'✅' if self.serper_key else '❌ (Scraplingフォールバック)'}")
        log.info(f"   Firecrawl: {'✅' if self.firecrawl_key else '❌ (Gemini直接分析)'}")
        log.info(f"   Scrapling: {'✅' if HAS_SCRAPLING else '❌'}")
        log.info("=" * 60)

        # ── Step 1: キーワード生成 ──
        log.info("\n📝 Step 1: スモールキーワード生成")
        queries = self.kw_gen.generate_all(
            self.cfg["big_keywords"], self.cfg["small_keyword_count"]
        )
        log.info(f"   → {len(queries)} クエリ生成")

        # 日次上限 + シャッフル
        if len(queries) > self.cfg["daily_query_limit"]:
            random.shuffle(queries)
            queries = queries[:self.cfg["daily_query_limit"]]
            log.info(f"   → {len(queries)} クエリに制限（日次ローテーション）")

        # ── Step 2: 検索 ──
        log.info("\n🔍 Step 2: 検索結果取得")
        all_results = []
        seen_urls = set()
        exclude = set(self.cfg["exclude_domains"])

        for i, q in enumerate(queries):
            log.info(f"  [{i+1}/{len(queries)}] {q['query']}")

            if self.searcher:
                results = self.searcher.search(q["query"], self.cfg["search_top_n"])
            else:
                log.info("    → Serper未設定、スキップ")
                results = []

            for r in results:
                url = r["url"]
                domain = urlparse(url).netloc.lower()
                if (url not in seen_urls
                    and not self.stock.has_url(url)
                    and not any(ex in domain for ex in exclude)):
                    seen_urls.add(url)
                    r["query"] = q["query"]
                    r["big_keyword"] = q["big_keyword"]
                    all_results.append(r)

            time.sleep(0.5)  # Serperは高速なので短い待機でOK

        log.info(f"   → 新規URL: {len(all_results)}件")

        # ── Step 3: デザイン分析 ──
        log.info("\n🎨 Step 3: デザイン分析")
        targets = all_results[:self.cfg["max_analysis_per_run"]]
        new_entries = []

        for i, result in enumerate(targets):
            url = result["url"]
            log.info(f"  [{i+1}/{len(targets)}] {result['domain']}")

            entry = DesignEntry(
                id=hashlib.md5(url.encode()).hexdigest()[:12],
                url=url,
                domain=result["domain"],
                title=result.get("title", ""),
                search_query=result.get("query", ""),
                search_rank=result.get("rank", 0),
                discovered_at=datetime.now().isoformat(),
            )

            branding_data = {}
            content_snippet = ""

            # 3a: Firecrawl でブランディングデータ取得
            if self.firecrawl:
                fc_result = self.firecrawl.extract(url)
                if fc_result["success"]:
                    branding_data = fc_result.get("branding", {})
                    content_snippet = fc_result.get("markdown", "")

                    entry.brand_colors = branding_data.get("colors", {})
                    entry.brand_fonts = branding_data.get("fonts", [])
                    entry.brand_typography = branding_data.get("typography", {})
                    entry.brand_spacing = branding_data.get("spacing", {})
                    entry.brand_logo = branding_data.get("logo", {})
                    entry.brand_ui_components = branding_data.get("ui_components", [])
                    entry.data_source = "firecrawl"

                    meta = fc_result.get("metadata", {})
                    if meta.get("title"):
                        entry.title = meta["title"]

            # 3b: Firecrawl失敗時 → Scraplingフォールバック
            if not branding_data and HAS_SCRAPLING:
                sc_result = self.scrapling_fb.fetch(url)
                if sc_result.get("success"):
                    content_snippet = sc_result.get("html", "")[:3000]
                    entry.title = entry.title or sc_result.get("title", "")
                    entry.data_source = "scrapling"

            if not branding_data and not content_snippet:
                log.info(f"    → スキップ（データ取得失敗）")
                continue

            # 3c: Gemini 補足分析
            analysis = self.analyzer.analyze(
                url, entry.title, branding_data, content_snippet
            )

            if analysis:
                entry.aesthetic = analysis.get("aesthetic", "")
                entry.overview = analysis.get("overview", "")
                entry.design_score = analysis.get("design_score", 0)
                entry.industry = analysis.get("industry", "")
                entry.tags = analysis.get("tags", [])
                entry.layout = analysis.get("layout", {})
                entry.effects = analysis.get("effects", {})
                entry.standout_elements = analysis.get("standout_elements", [])
                entry.design_principles = analysis.get("design_principles", [])
                entry.reuse_tips = analysis.get("reuse_tips", [])

            # スコアフィルタ
            if entry.design_score >= self.cfg["min_design_score"]:
                self.stock.add(entry)
                new_entries.append(entry)
                log.info(f"    ✅ [{entry.design_score}] {entry.aesthetic} ({entry.data_source})")

                # Supabase にも同期
                if self.supabase:
                    self.supabase.upsert(entry.to_dict())

                # 📸 スクリーンショット撮影
                if self.monitor:
                    ss = self.monitor.capture_screenshot(url, entry.id)
                    if ss.get("success"):
                        entry.screenshot_path = ss.get("path", "")
            else:
                log.info(f"    ⏭️ [{entry.design_score}] スコア不足")

            time.sleep(1.5)

        # ── Step 4: トレンドレポート ──
        log.info("\n📊 Step 4: トレンドレポート")
        self.stock.export_trend_report()

        # ── Step 5: 既存サイトの変化検知 ──
        change_results = {"checked": 0, "changed": 0}
        if self.monitor and self.cfg.get("enable_change_detection", True):
            log.info("\n🔄 Step 5: デザイン変化検知")
            max_checks = self.cfg.get("change_detection_limit", 10)
            diffs = self.monitor.run_change_detection(max_checks)
            change_results = {
                "checked": len(diffs),
                "changed": sum(1 for d in diffs if d.change_level != "none"),
            }

        # ── 結果記録 ──
        elapsed = (datetime.now() - start).total_seconds()
        summary = {
            "date": datetime.now().isoformat(),
            "queries": len(queries),
            "urls_found": len(all_results),
            "analyzed": len(targets),
            "stocked": len(new_entries),
            "elapsed_sec": round(elapsed),
            "avg_score": round(
                sum(e.design_score for e in new_entries) / len(new_entries), 1
            ) if new_entries else 0,
            "api_usage": {
                "serper_queries": len(queries) if self.serper_key else 0,
                "firecrawl_scrapes": sum(1 for e in new_entries if "firecrawl" in e.data_source),
                "gemini_calls": len(queries) + len(targets),
            },
            "screenshots": sum(1 for e in new_entries if getattr(e, "screenshot_path", "")),
            "change_detection": change_results,
        }
        self.stock.add_run(summary)

        # ── サマリー ──
        log.info("\n" + "=" * 60)
        log.info("📊 実行結果")
        log.info("=" * 60)
        log.info(f"  検索クエリ:     {summary['queries']}")
        log.info(f"  新規URL発見:    {summary['urls_found']}")
        log.info(f"  分析実行:       {summary['analyzed']}")
        log.info(f"  新規ストック:   {summary['stocked']}")
        log.info(f"  平均スコア:     {summary['avg_score']}")
        log.info(f"  総ストック:     {self.stock.index.get('total', 0)}")
        log.info(f"  所要時間:       {summary['elapsed_sec']}秒")
        log.info(f"  --- API使用量 ---")
        log.info(f"  Serper:         {summary['api_usage']['serper_queries']}クエリ")
        log.info(f"  Firecrawl:      {summary['api_usage']['firecrawl_scrapes']}スクレイプ")
        log.info(f"  Gemini:         {summary['api_usage']['gemini_calls']}コール")
        log.info(f"  --- モニタリング ---")
        log.info(f"  スクリーンショット: {summary['screenshots']}枚")
        log.info(f"  変化チェック:   {change_results['checked']}件 / 変化: {change_results['changed']}件")
        log.info("=" * 60)

        if new_entries:
            log.info("\n🏆 本日のTOP 5:")
            for i, e in enumerate(sorted(new_entries, key=lambda x: x.design_score, reverse=True)[:5]):
                log.info(f"  {i+1}. [{e.design_score}] {e.aesthetic} - {e.domain}")

        return summary


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="デザイン自動調査 v2")
    parser.add_argument("--config", "-c", default="config_v2.json")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--check-changes", action="store_true", help="変化検知のみ実行")
    parser.add_argument("--screenshot", type=str, help="指定URLのスクリーンショット")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.report_only:
        DesignStock(cfg["output_dir"]).export_trend_report()
    elif args.check_changes:
        try:
            from design_monitor import DesignMonitor
            m = DesignMonitor(
                firecrawl_key=os.getenv("FIRECRAWL_API_KEY", ""),
                gemini_key=os.getenv("GEMINI_API_KEY", ""),
                stock_dir=cfg["output_dir"],
            )
            diffs = m.run_change_detection(cfg.get("change_detection_limit", 20))
            changed = [d for d in diffs if d.change_level != "none"]
            log.info(f"結果: {len(changed)}件の変化を検知")
        except ImportError:
            log.error("design_monitor.py が見つかりません")
    elif args.screenshot:
        try:
            from design_monitor import DesignMonitor
            m = DesignMonitor(firecrawl_key=os.getenv("FIRECRAWL_API_KEY", ""), stock_dir=cfg["output_dir"])
            eid = hashlib.md5(args.screenshot.encode()).hexdigest()[:12]
            result = m.capture_screenshot(args.screenshot, eid)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except ImportError:
            log.error("design_monitor.py が見つかりません")
    else:
        DesignResearchPipelineV2(cfg).run()
