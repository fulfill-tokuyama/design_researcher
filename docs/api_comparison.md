# API & MCP 調査結果（2026-03-06）

## デザイン抽出系

### Firecrawl Branding Format ★★★★★
- URLを渡すだけでカラー・フォント・タイポグラフィ・スペーシング・UIコンポーネントを構造化抽出
- screenshot フォーマットでフルページスクリーンショットも取得可能
- MCP サーバーあり（Claude Desktop / Cursor対応）
- 料金: 無料枠あり → Hobby $16/月
- 採用: ✅ design_research/ に組み込み済み

### Scrapling MCP Server ★★★★
- 6ツール（get, bulk_get, fetch, bulk_fetch等）
- CSSセレクタで要素を絞り込んでからAIに渡す → トークン節約
- Cloudflare Turnstile バイパス対応
- 料金: OSS無料
- 採用: ✅ lead_scraper/ + design_research/ のフォールバック

## 検索系

### Serper.dev ★★★★★
- Google検索結果を1-2秒でJSON返却
- 無料2,500クエリ（永久）、有料は$1/1,000クエリ〜
- MCP サーバーあり
- 採用: ✅ design_research/ に組み込み済み

### SerpAPI ★★★★
- 80以上の検索エンジン対応（Google, Bing, Baidu等）
- 無料100クエリ/月、有料 $75/月〜
- Serperより高価だが多機能
- 採用: ❌ Serperで十分なため不採用

### Google Custom Search API ★★★
- 1日100クエリまで無料、超過$5/1,000クエリ
- 結果の質がSerperに劣る
- 採用: ❌

## ブラウザ自動化 / スクレイピング系

### Bright Data MCP Server ★★★
- SERP API + ブラウザAPI + プロキシ回転を統合
- CAPTCHA自動解決
- 月5,000リクエスト無料
- 採用: ❌ Scrapling + Firecrawl の組み合わせで代替可能

### Crawl4AI MCP Server ★★★
- Gemini連携のsmart_extract機能
- Docker対応
- 採用: ❌ Scraplingで代替

## LP生成の改善候補（未実装）

### Supabase pgvector
- ストックデザインのベクトル類似検索
- 既存のSupabase利用（AIO Insight）と統合可能
- 優先度: 高（次回実装候補）
