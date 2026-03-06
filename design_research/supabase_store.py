"""
LeadGenius Design Suite - Supabase連携モジュール
================================================

機能:
  1. デザインストックの永続化（ローカルJSON → Supabase PostgreSQL）
  2. pgvector によるベクトル類似検索（「このサイトに似たデザイン」）
  3. Gemini Embedding でデザイン特徴をベクトル化
  4. ローカルストック ↔ Supabase の双方向同期

環境変数:
    SUPABASE_URL       : Supabase プロジェクトURL
    SUPABASE_KEY       : Supabase anon key（または service_role key）
    GEMINI_API_KEY     : Gemini API キー（embedding生成用）

セットアップ:
    pip install supabase google-genai
    python supabase_store.py --init       # テーブル作成
    python supabase_store.py --sync       # ローカル → Supabase同期
    python supabase_store.py --search "ミニマル ダーク SaaS"
"""

import json
import os
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

# .env をプロジェクトルートから読み込み
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

log = logging.getLogger("design_v2.supabase")


# =============================================================================
# スキーマ定義（SQL）
# =============================================================================

SCHEMA_SQL = """
-- pgvector 拡張を有効化
CREATE EXTENSION IF NOT EXISTS vector;

-- デザインストックテーブル
CREATE TABLE IF NOT EXISTS design_entries (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    domain TEXT,
    title TEXT,
    search_query TEXT,
    search_rank INTEGER DEFAULT 0,
    discovered_at TIMESTAMPTZ DEFAULT NOW(),

    -- Firecrawl Branding
    brand_colors JSONB DEFAULT '{}',
    brand_fonts JSONB DEFAULT '[]',
    brand_typography JSONB DEFAULT '{}',
    brand_spacing JSONB DEFAULT '{}',
    brand_logo JSONB DEFAULT '{}',

    -- Gemini 分析
    aesthetic TEXT,
    overview TEXT,
    design_score REAL DEFAULT 0,
    industry TEXT,
    tags TEXT[] DEFAULT '{}',
    layout JSONB DEFAULT '{}',
    effects JSONB DEFAULT '{}',
    standout_elements TEXT[] DEFAULT '{}',
    design_principles TEXT[] DEFAULT '{}',
    reuse_tips TEXT[] DEFAULT '{}',

    -- メタ
    data_source TEXT,
    screenshot_path TEXT,
    last_change_detected TIMESTAMPTZ,
    change_history JSONB DEFAULT '[]',

    -- ベクトル（Gemini embedding-001: 768次元）
    embedding VECTOR(768),

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_design_score ON design_entries (design_score DESC);
CREATE INDEX IF NOT EXISTS idx_industry ON design_entries (industry);
CREATE INDEX IF NOT EXISTS idx_discovered ON design_entries (discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_tags ON design_entries USING GIN (tags);

-- ベクトル検索用 HNSW インデックス（高速近似検索）
CREATE INDEX IF NOT EXISTS idx_embedding_hnsw
ON design_entries USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 類似検索関数
CREATE OR REPLACE FUNCTION match_designs(
    query_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10,
    filter_industry TEXT DEFAULT NULL,
    min_score FLOAT DEFAULT 0
)
RETURNS TABLE(
    id TEXT,
    url TEXT,
    domain TEXT,
    aesthetic TEXT,
    design_score REAL,
    industry TEXT,
    tags TEXT[],
    overview TEXT,
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        d.id, d.url, d.domain, d.aesthetic,
        d.design_score, d.industry, d.tags, d.overview,
        1 - (d.embedding <=> query_embedding) AS similarity
    FROM design_entries d
    WHERE
        d.embedding IS NOT NULL
        AND 1 - (d.embedding <=> query_embedding) > match_threshold
        AND d.design_score >= min_score
        AND (filter_industry IS NULL OR d.industry = filter_industry)
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- 更新日時自動更新トリガー
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_updated_at ON design_entries;
CREATE TRIGGER trigger_updated_at
    BEFORE UPDATE ON design_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- 変化検知履歴テーブル
CREATE TABLE IF NOT EXISTS design_changes (
    id SERIAL PRIMARY KEY,
    entry_id TEXT REFERENCES design_entries(id),
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    change_level TEXT,
    change_score REAL DEFAULT 0,
    summary TEXT,
    color_changes JSONB DEFAULT '[]',
    font_changes JSONB DEFAULT '[]',
    layout_changes JSONB DEFAULT '[]',
    previous_aesthetic TEXT,
    current_aesthetic TEXT
);

CREATE INDEX IF NOT EXISTS idx_changes_entry ON design_changes (entry_id);
CREATE INDEX IF NOT EXISTS idx_changes_date ON design_changes (detected_at DESC);

-- トレンドレポートテーブル
CREATE TABLE IF NOT EXISTS trend_reports (
    id SERIAL PRIMARY KEY,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    report_data JSONB NOT NULL
);
"""


# =============================================================================
# Embedding 生成（Gemini）
# =============================================================================

class DesignEmbedder:
    """デザイン特徴をベクトル化"""

    def __init__(self, api_key: str):
        if not HAS_GENAI:
            raise ImportError("google-genai が必要です")
        self.client = genai.Client(api_key=api_key)

    def create_embedding(self, entry: dict) -> list[float]:
        """
        デザインエントリの特徴をテキスト化 → embedding生成

        ベクトル化する情報:
        - aesthetic（デザインスタイル名）
        - overview（概要）
        - カラーパレット
        - フォント
        - タグ
        - standout_elements
        - industry
        """
        # デザイン特徴をテキストに変換
        parts = []

        if entry.get("aesthetic"):
            parts.append(f"デザインスタイル: {entry['aesthetic']}")
        if entry.get("overview"):
            parts.append(f"概要: {entry['overview']}")
        if entry.get("industry"):
            parts.append(f"業界: {entry['industry']}")

        # カラー
        colors = entry.get("brand_colors", {})
        if colors:
            color_strs = [f"{k}: {v}" for k, v in colors.items() if isinstance(v, str)]
            if color_strs:
                parts.append(f"カラー: {', '.join(color_strs)}")

        # フォント
        fonts = entry.get("brand_fonts", [])
        if fonts:
            parts.append(f"フォント: {', '.join(str(f) for f in fonts[:5])}")

        # タグ
        tags = entry.get("tags", [])
        if tags:
            parts.append(f"タグ: {', '.join(tags)}")

        # 特徴要素
        standout = entry.get("standout_elements", [])
        if standout:
            parts.append(f"特徴: {', '.join(standout[:5])}")

        # デザイン原則
        principles = entry.get("design_principles", [])
        if principles:
            parts.append(f"原則: {', '.join(principles[:5])}")

        text = "\n".join(parts)
        if not text.strip():
            text = f"Webサイト: {entry.get('url', '')} {entry.get('domain', '')}"

        return self._embed(text)

    def create_query_embedding(self, query: str) -> list[float]:
        """検索クエリ用のembedding生成"""
        return self._embed(query)

    def _embed(self, text: str) -> list[float]:
        """Gemini embedding API呼び出し"""
        try:
            result = self.client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=768),
            )
            return result.embeddings[0].values
        except Exception as e:
            log.warning(f"Embedding生成失敗: {e}")
            return []


# =============================================================================
# Supabase ストア
# =============================================================================

class SupabaseDesignStore:
    """Supabaseベースのデザインストック管理"""

    def __init__(
        self,
        supabase_url: str = "",
        supabase_key: str = "",
        gemini_key: str = "",
    ):
        self.url = supabase_url or os.getenv("SUPABASE_URL", "")
        self.key = supabase_key or os.getenv("SUPABASE_KEY", "")
        self.gemini_key = gemini_key or os.getenv("GEMINI_API_KEY", "")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL と SUPABASE_KEY を設定してください")

        if HAS_SUPABASE:
            self.client: Client = create_client(self.url, self.key)
        else:
            self.client = None
            log.warning("supabase パッケージ未インストール。REST APIで代替します。")

        self.embedder = DesignEmbedder(self.gemini_key) if self.gemini_key and HAS_GENAI else None

    # ─── スキーマ初期化 ───
    def init_schema(self):
        """テーブル・インデックス・関数を作成"""
        log.info("📦 Supabase スキーマ初期化")

        # Supabase SQL Editor で実行するSQLを出力
        print("=" * 60)
        print("以下のSQLを Supabase Dashboard > SQL Editor で実行してください:")
        print("=" * 60)
        print(SCHEMA_SQL)
        print("=" * 60)

        # スキーマSQLをファイルにも保存（UTF-8で文字化け防止）
        path = Path("supabase_schema.sql")
        path.write_text(SCHEMA_SQL, encoding="utf-8")
        log.info(f"📄 SQLファイル保存: {path}")

    # ─── CRUD ───
    def upsert(self, entry: dict) -> bool:
        """エントリを挿入/更新（embedding付き）"""
        try:
            # Embedding生成
            embedding = None
            if self.embedder:
                embedding = self.embedder.create_embedding(entry)

            record = {
                "id": entry.get("id", ""),
                "url": entry.get("url", ""),
                "domain": entry.get("domain", ""),
                "title": entry.get("title", ""),
                "search_query": entry.get("search_query", ""),
                "search_rank": entry.get("search_rank", 0),
                "discovered_at": entry.get("discovered_at", datetime.now().isoformat()),
                "brand_colors": json.dumps(entry.get("brand_colors", {})),
                "brand_fonts": json.dumps(entry.get("brand_fonts", [])),
                "brand_typography": json.dumps(entry.get("brand_typography", {})),
                "brand_spacing": json.dumps(entry.get("brand_spacing", {})),
                "brand_logo": json.dumps(entry.get("brand_logo", {})),
                "aesthetic": entry.get("aesthetic", ""),
                "overview": entry.get("overview", ""),
                "design_score": entry.get("design_score", 0),
                "industry": entry.get("industry", ""),
                "tags": entry.get("tags", []),
                "layout": json.dumps(entry.get("layout", {})),
                "effects": json.dumps(entry.get("effects", {})),
                "standout_elements": entry.get("standout_elements", []),
                "design_principles": entry.get("design_principles", []),
                "reuse_tips": entry.get("reuse_tips", []),
                "data_source": entry.get("data_source", ""),
                "screenshot_path": entry.get("screenshot_path", ""),
            }

            if embedding:
                record["embedding"] = embedding

            if self.client:
                self.client.table("design_entries").upsert(record).execute()
            else:
                self._rest_upsert("design_entries", record)

            return True

        except Exception as e:
            log.warning(f"Supabase upsert失敗: {e}")
            return False

    def get_entry(self, entry_id: str) -> Optional[dict]:
        """IDでエントリ取得"""
        try:
            if self.client:
                resp = self.client.table("design_entries").select("*").eq("id", entry_id).execute()
                return resp.data[0] if resp.data else None
            return None
        except Exception as e:
            log.warning(f"取得失敗: {e}")
            return None

    def get_all(self, limit: int = 100, min_score: float = 0) -> list[dict]:
        """全エントリ取得（スコア順）"""
        try:
            if self.client:
                resp = (
                    self.client.table("design_entries")
                    .select("*")
                    .gte("design_score", min_score)
                    .order("design_score", desc=True)
                    .limit(limit)
                    .execute()
                )
                return resp.data
            return []
        except Exception as e:
            log.warning(f"取得失敗: {e}")
            return []

    # ─── ベクトル類似検索 ───
    def search_similar(
        self,
        query: str,
        threshold: float = 0.5,
        limit: int = 10,
        industry: str = None,
        min_score: float = 0,
    ) -> list[dict]:
        """
        自然言語クエリで類似デザインを検索

        例:
            store.search_similar("ダークテーマ ミニマル SaaS")
            store.search_similar("stripe.comのような洗練されたデザイン")
            store.search_similar("不動産 信頼感 グリーン系")
        """
        if not self.embedder:
            log.warning("Gemini APIキー未設定。ベクトル検索不可")
            return []

        query_embedding = self.embedder.create_query_embedding(query)
        if not query_embedding:
            return []

        try:
            if self.client:
                params = {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": limit,
                    "min_score": min_score,
                }
                if industry:
                    params["filter_industry"] = industry

                resp = self.client.rpc("match_designs", params).execute()
                return resp.data
            return []

        except Exception as e:
            err_str = str(e)
            if "404" in err_str or "NOT_FOUND" in err_str:
                log.info("RPC 404 → ローカル類似度計算でフォールバック")
                return self._search_similar_fallback(
                    query_embedding, threshold, limit, industry, min_score
                )
            else:
                log.warning(f"ベクトル検索失敗: {e}")
            return []

    def _search_similar_fallback(
        self,
        query_embedding: list[float],
        threshold: float,
        limit: int,
        industry: str = None,
        min_score: float = 0,
    ) -> list[dict]:
        """RPC失敗時: 全エントリ取得してPythonで類似度計算"""
        try:
            if not self.client:
                return []
            resp = (
                self.client.table("design_entries")
                .select("id, url, domain, aesthetic, design_score, industry, tags, overview, embedding")
                .not_.is_("embedding", "null")
                .gte("design_score", min_score)
                .limit(500)
                .execute()
            )
            entries = resp.data or []
            if industry:
                entries = [e for e in entries if e.get("industry") == industry]

            def cosine_sim(a: list, b: list) -> float:
                if not a or not b or len(a) != len(b):
                    return 0.0
                dot = sum(x * y for x, y in zip(a, b))
                na = sum(x * x for x in a) ** 0.5
                nb = sum(x * x for x in b) ** 0.5
                if na == 0 or nb == 0:
                    return 0.0
                return dot / (na * nb)

            scored = []
            for e in entries:
                emb = e.get("embedding")
                if isinstance(emb, str):
                    try:
                        emb = json.loads(emb)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if isinstance(emb, list) and len(emb) == len(query_embedding):
                    sim = cosine_sim(query_embedding, emb)
                else:
                    continue
                if sim >= threshold:
                    scored.append({
                        **{k: v for k, v in e.items() if k != "embedding"},
                        "similarity": round(sim, 4),
                    })
            scored.sort(key=lambda x: x["similarity"], reverse=True)
            return scored[:limit]
        except Exception as e:
            log.warning(f"フォールバック検索失敗: {e}")
            return []

    def search_similar_to_entry(
        self,
        entry_id: str,
        limit: int = 5,
        threshold: float = 0.6,
    ) -> list[dict]:
        """既存エントリに類似したデザインを検索"""
        entry = self.get_entry(entry_id)
        if not entry:
            return []

        # エントリの特徴テキストからクエリ生成
        query_parts = [
            entry.get("aesthetic", ""),
            entry.get("overview", ""),
            " ".join(entry.get("tags", [])),
        ]
        query = " ".join(filter(None, query_parts))

        results = self.search_similar(query, threshold, limit + 1)
        # 自身を除外
        return [r for r in results if r["id"] != entry_id][:limit]

    # ─── ローカル ↔ Supabase 同期 ───
    def sync_from_local(self, stock_dir: str = "./design_stock_v2"):
        """ローカルJSONストック → Supabase に同期"""
        stock_path = Path(stock_dir)
        index_path = stock_path / "index.json"

        if not index_path.exists():
            log.warning(f"ローカルストックが見つかりません: {index_path}")
            return

        index = json.loads(index_path.read_text(encoding="utf-8"))
        entries = index.get("entries", {})
        total = len(entries)
        success = 0

        log.info(f"📤 ローカル → Supabase 同期開始 ({total}件)")

        for i, (entry_id, meta) in enumerate(entries.items()):
            detail_path = stock_path / f"{entry_id}.json"
            if detail_path.exists():
                entry = json.loads(detail_path.read_text(encoding="utf-8"))
            else:
                entry = meta
                entry["id"] = entry_id

            if self.upsert(entry):
                success += 1

            if (i + 1) % 10 == 0:
                log.info(f"  [{i+1}/{total}] {success}件成功")

        log.info(f"✅ 同期完了: {success}/{total}件")

    def sync_to_local(self, stock_dir: str = "./design_stock_v2"):
        """Supabase → ローカルJSON に同期"""
        stock_path = Path(stock_dir)
        stock_path.mkdir(parents=True, exist_ok=True)

        entries = self.get_all(limit=1000)
        if not entries:
            log.info("Supabaseにデータなし")
            return

        log.info(f"📥 Supabase → ローカル同期 ({len(entries)}件)")

        index = {"entries": {}, "created_at": datetime.now().isoformat()}

        for entry in entries:
            eid = entry["id"]
            detail_path = stock_path / f"{eid}.json"
            detail_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

            index["entries"][eid] = {
                "url": entry.get("url", ""),
                "domain": entry.get("domain", ""),
                "aesthetic": entry.get("aesthetic", ""),
                "design_score": entry.get("design_score", 0),
                "industry": entry.get("industry", ""),
                "tags": entry.get("tags", []),
                "discovered_at": str(entry.get("discovered_at", "")),
            }

        index["total"] = len(index["entries"])
        index_path = stock_path / "index.json"
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

        log.info(f"✅ ローカル同期完了: {len(entries)}件")

    # ─── REST API フォールバック ───
    def _rest_upsert(self, table: str, record: dict):
        """supabaseパッケージなしのREST APIフォールバック"""
        resp = requests.post(
            f"{self.url}/rest/v1/{table}",
            headers={
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
            json=record,
            timeout=10,
        )
        resp.raise_for_status()

    # ─── 統計 ───
    def get_stats(self) -> dict:
        """ストックの統計情報"""
        try:
            if self.client:
                # 総数
                total_resp = self.client.table("design_entries").select("id", count="exact").execute()
                total = total_resp.count or 0

                # embedding済み
                embed_resp = (
                    self.client.table("design_entries")
                    .select("id", count="exact")
                    .not_.is_("embedding", "null")
                    .execute()
                )
                embedded = embed_resp.count or 0

                # 業界別
                entries = self.client.table("design_entries").select("industry, design_score").execute()
                industry_map = {}
                scores = []
                for e in entries.data:
                    ind = e.get("industry", "不明")
                    industry_map[ind] = industry_map.get(ind, 0) + 1
                    scores.append(e.get("design_score", 0))

                return {
                    "total": total,
                    "embedded": embedded,
                    "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
                    "industries": industry_map,
                }
            return {}
        except Exception as e:
            log.warning(f"統計取得失敗: {e}")
            return {}


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Supabase デザインストア")
    parser.add_argument("--init", action="store_true", help="スキーマSQL出力")
    parser.add_argument("--sync", action="store_true", help="ローカル → Supabase同期")
    parser.add_argument("--sync-back", action="store_true", help="Supabase → ローカル同期")
    parser.add_argument("--search", type=str, help="類似デザイン検索")
    parser.add_argument("--similar-to", type=str, help="指定IDに類似したデザイン検索")
    parser.add_argument("--stats", action="store_true", help="統計表示")
    parser.add_argument("--stock-dir", default="./design_stock_v2")
    args = parser.parse_args()

    if args.init:
        store = SupabaseDesignStore.__new__(SupabaseDesignStore)
        store.init_schema = lambda: (
            print("=" * 60),
            print("以下のSQLを Supabase SQL Editor で実行:"),
            print("=" * 60),
            print(SCHEMA_SQL),
            Path("supabase_schema.sql").write_text(SCHEMA_SQL, encoding="utf-8"),
            print(f"\n📄 supabase_schema.sql に保存しました"),
        )
        store.init_schema()
    else:
        store = SupabaseDesignStore()

        if args.sync:
            store.sync_from_local(args.stock_dir)
        elif args.sync_back:
            store.sync_to_local(args.stock_dir)
        elif args.search:
            log.info(f'🔍 検索: "{args.search}"')
            results = store.search_similar(args.search, threshold=0.4, limit=10)
            if results:
                for i, r in enumerate(results):
                    sim = r.get("similarity", 0)
                    log.info(f"  {i+1}. [{r['design_score']}] {r['aesthetic']} - {r['domain']} (類似度: {sim:.2f})")
            else:
                log.info("  結果なし")
        elif args.similar_to:
            log.info(f"🔍 類似検索: ID={args.similar_to}")
            results = store.search_similar_to_entry(args.similar_to)
            for i, r in enumerate(results):
                log.info(f"  {i+1}. [{r['design_score']}] {r['aesthetic']} - {r['domain']}")
        elif args.stats:
            stats = store.get_stats()
            log.info(f"📊 統計:")
            log.info(f"  総数: {stats.get('total', 0)}")
            log.info(f"  ベクトル化済み: {stats.get('embedded', 0)}")
            log.info(f"  平均スコア: {stats.get('avg_score', 0)}")
            log.info(f"  業界別: {json.dumps(stats.get('industries', {}), ensure_ascii=False)}")
        else:
            parser.print_help()
