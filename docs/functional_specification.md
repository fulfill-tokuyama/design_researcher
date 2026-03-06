# LeadGenius Design Suite - 機能仕様書

| 項目 | 内容 |
|------|------|
| プロジェクト名 | LeadGenius Design Suite |
| 運営 | Fulfill株式会社 |
| バージョン | 2.0 |
| 最終更新日 | 2026-03-06 |

---

## 1. 概要

### 1.1 目的

LeadGenius Design Suiteは、以下の3つの業務を自動化・効率化する統合ツールキットである。

1. **デザイン自動調査** — Webデザインのトレンドを毎日自動収集・分析・ストックする
2. **リード収集パイプライン** — 企業Webサイトからリード情報を収集し、AIスコアリング・メール送信まで一気通貫で行う
3. **LP自動生成** — ストックしたデザインを参考に、AIでランディングページを生成・編集する

### 1.2 対象サービス

- LeadGenius AI（リード収集・営業自動化）
- AIO Insight（AI検索最適化サービス）
- BeginAI（AIワークショップ）

### 1.3 システム構成図

```
+-------------------------------------------------------------------+
|                    LeadGenius Design Suite                         |
+-------------------+----------------------+------------------------+
|  lead_scraper/    |  design_research/    |  design_studio/        |
|                   |                      |                        |
|  Scrapling        |  Serper -> Firecrawl |  Design Studio (React) |
|  Spider で        |  -> Gemini で        |  参考URL -> デザインDNA |
|  企業情報収集     |  デザイン自動収集    |  -> LP生成             |
|       |           |       |              |                        |
|  Gemini で        |  ストック +          |  LP Builder (React)    |
|  スコアリング     |  変化検知 +          |  セクション分割編集    |
|       |           |  スクリーンショット  |  ドラッグ並び替え      |
|  Resend で        |       |              |  AI修正指示            |
|  メール送信       |  トレンドレポート    |  HTMLダウンロード      |
+-------------------+----------------------+------------------------+
|                                                                   |
|  Supabase (PostgreSQL + pgvector)  永続化・ベクトル類似検索       |
|  n8n ワークフロー                  外部連携・通知自動化           |
+-------------------------------------------------------------------+
```

---

## 2. モジュール別機能仕様

---

### 2.1 design_research/ — デザイン自動調査

#### 2.1.1 概要

おしゃれなWebデザインをインターネットから毎日自動収集し、カラー・フォント・レイアウト等のデザイン要素を構造化データとしてストックする。

#### 2.1.2 構成ファイル

| ファイル | 責務 |
|----------|------|
| `design_researcher_v2.py` | メインパイプライン（5ステップ統合実行） |
| `design_monitor.py` | スクリーンショット撮影 + デザイン変化検知 + 通知 |
| `scheduler_v2.py` | 定時実行スケジューラー（cron / systemd / 常駐） |
| `supabase_store.py` | Supabase連携（永続化・ベクトル類似検索） |
| `config.json` | 実行設定（キーワード・API設定・フィルタ） |

#### 2.1.3 パイプラインフロー

**Step 1: スモールキーワード生成**

| 項目 | 内容 |
|------|------|
| 入力 | config.jsonのbig_keywords（8個） |
| 処理 | Gemini APIで各ビッグKWからスモールKWを自動生成 |
| 出力 | クエリリスト（ビッグKW + スモールKW の組み合わせ） |
| 制約 | 日次クエリ上限: 15（daily_query_limit） |
| 備考 | 上限超過時はシャッフルしてローテーション選択 |

**Step 2: 検索結果取得**

| 項目 | 内容 |
|------|------|
| 入力 | Step 1のクエリリスト |
| 処理 | Serper.dev APIでGoogle検索TOP N件のURLを取得 |
| 出力 | 新規URLリスト（重複・既存ストック・除外ドメインを排除） |
| パラメータ | search_top_n: 10, serper_gl: "jp", serper_hl: "ja" |
| 除外ドメイン | pinterest.com, youtube.com, twitter.com, x.com, facebook.com, instagram.com, amazon.co.jp, rakuten.co.jp, wikipedia.org, note.com, qiita.com, zenn.dev, hatena.ne.jp, matome.naver.jp |

**Step 3: デザイン分析**

| 項目 | 内容 |
|------|------|
| 入力 | Step 2の新規URLリスト |
| 処理 | 3段階の分析 |
| 3a | Firecrawl Branding APIでカラー/フォント/タイポグラフィ/スペーシング/ロゴ/UIコンポーネントを構造化抽出 |
| 3b | Firecrawl失敗時: Scraplingでフォールバック取得 |
| 3c | Gemini APIで補足分析（美的スタイル名・スコアリング・タグ・レイアウト・エフェクト等） |
| 出力 | DesignEntryオブジェクト |
| フィルタ | design_score >= 50（min_design_score）のもののみストック |
| 制約 | max_analysis_per_run: 30 |

**Step 3 補足: スクリーンショット撮影**

| 項目 | 内容 |
|------|------|
| トリガー | スコアフィルタ通過後 |
| 方法 | Firecrawl Screenshot API（優先） / Scrapling DynamicFetcher（フォールバック） |
| 出力 | PNGファイル + サムネイル（400x300, PIL使用時） |
| 保存先 | design_stock_v2/screenshots/{entry_id}_{timestamp}.png |

**Step 4: トレンドレポート生成**

| 項目 | 内容 |
|------|------|
| 処理 | ストック全体を集計 |
| 出力内容 | 総数・平均スコア・トレンドタグTOP20・トレンドスタイルTOP15・業界分布・TOP10サイト |
| 出力先 | design_stock_v2/trend_YYYYMMDD.json |

**Step 5: デザイン変化検知**

| 項目 | 内容 |
|------|------|
| 処理 | 既存ストックサイトを再スクレイプし、前回データとの差分を検出 |
| 比較方法 | カラー/フォントのハッシュ簡易比較 -> 変化あればGeminiで詳細分析 |
| 変化レベル | major（大幅リデザイン）/ minor（部分変更）/ none（変化なし） |
| 通知 | major/minor検知時にDiscord/Slack Webhookで通知 |
| 更新 | major検知時はストックデータを自動更新 |
| 制約 | change_detection_limit: 10（スコア上位から優先チェック） |

#### 2.1.4 データモデル: DesignEntry

| フィールド | 型 | 説明 |
|---|---|---|
| id | string | URL のMD5ハッシュ先頭12文字 |
| url | string | サイトURL |
| domain | string | ドメイン名 |
| title | string | ページタイトル |
| search_query | string | 発見時の検索クエリ |
| search_rank | int | 検索結果での順位 |
| discovered_at | string (ISO8601) | 発見日時 |
| brand_colors | dict | カラーパレット（Firecrawl抽出） |
| brand_fonts | list | 使用フォント一覧 |
| brand_typography | dict | タイポグラフィ設定 |
| brand_spacing | dict | スペーシング設定 |
| brand_logo | dict | ロゴ情報 |
| brand_ui_components | list | UIコンポーネント一覧 |
| aesthetic | string | デザインスタイル名（例: "ミニマル・プレミアム"） |
| overview | string | デザイン全体の印象（2-3文） |
| design_score | float | 品質スコア 0-100（独創性30%+統一感30%+完成度20%+トレンド性20%） |
| industry | string | 業界カテゴリ |
| tags | list[string] | デザインタグ（5個） |
| layout | dict | レイアウト情報（セクション一覧・グリッド・余白） |
| effects | dict | エフェクト情報（アニメーション・ホバー・背景） |
| standout_elements | list[string] | 特徴的なデザイン要素（5個） |
| design_principles | list[string] | デザイン原則（3-5個） |
| reuse_tips | list[string] | 参考にする際のポイント（3個） |
| data_source | string | データ取得元（"firecrawl" / "scrapling" / "both"） |
| screenshot_path | string | スクリーンショットファイルパス |

#### 2.1.5 ストック出力構造

```
design_stock_v2/
  index.json                    -- 全エントリのインデックス + 実行履歴
  {entry_id}.json               -- 各サイトの詳細分析データ
  trend_YYYYMMDD.json           -- トレンドレポート
  screenshots/
    {entry_id}_{timestamp}.png       -- フルスクリーンショット
    {entry_id}_{timestamp}_thumb.png -- サムネイル
  change_history/
    {entry_id}_{timestamp}.json      -- 変化検知ログ
```

#### 2.1.6 スケジューラー

| 実行方法 | コマンド |
|----------|----------|
| 常駐プロセス | `python scheduler_v2.py` (デフォルト毎日03:00) |
| cron設定出力 | `python scheduler_v2.py --setup-cron --hour 3` |
| systemd設定生成 | `python scheduler_v2.py --setup-systemd --hour 3` |
| 即時1回実行 | `python scheduler_v2.py --run-now` |

#### 2.1.7 設定パラメータ (config.json)

| パラメータ | デフォルト値 | 説明 |
|---|---|---|
| big_keywords | 8個 | ベースとなるビッグキーワード |
| small_keyword_count | 5 | ビッグKWあたりのスモールKW生成数 |
| daily_query_limit | 15 | 1日の検索クエリ上限 |
| search_top_n | 10 | 検索結果の取得件数 |
| max_analysis_per_run | 30 | 1回の分析上限 |
| gemini_model | "gemini-2.0-flash" | 使用するGeminiモデル |
| serper_gl | "jp" | Serper: 国コード |
| serper_hl | "ja" | Serper: 言語 |
| firecrawl_timeout | 30 | Firecrawl APIタイムアウト（秒） |
| exclude_domains | 14個 | 除外ドメインリスト |
| min_design_score | 50 | ストックする最低スコア |
| enable_change_detection | true | 変化検知の有効/無効 |
| change_detection_limit | 10 | 変化チェック上限 |
| output_dir | "./design_stock_v2" | 出力ディレクトリ |

---

### 2.2 lead_scraper/ — リード収集パイプライン

#### 2.2.1 概要

企業WebサイトからリードA情報を自動収集し、Gemini APIでスコアリング・パーソナライズドメール生成を行い、Resend APIでメール送信するまでの一気通貫パイプライン。

#### 2.2.2 構成ファイル

| ファイル | 責務 |
|----------|------|
| `lead_spider.py` | Scrapling Spiderによる企業情報スクレイピング |
| `lead_enricher.py` | Gemini APIによるスコアリング + メール文面生成 |
| `pipeline.py` | 統合パイプライン（収集 -> 分析 -> 送信 -> 出力） |
| `targets_sample.json` | ターゲットURLサンプル |

#### 2.2.3 パイプラインフロー

**Step 1: Webスクレイピング**

| 項目 | 内容 |
|------|------|
| 入力 | ターゲットURLリスト（JSONファイル） |
| Spider | CompanyWebsiteSpider（企業サイト直接収集） |
| 収集項目 | 社名・代表者名・住所・電話番号・メール・Webサイト・事業内容・免許番号・従業員数・設立年 |
| ページ遷移 | トップページ -> 会社概要ページを自動探索 |
| 抽出方法 | CSSセレクタ + テーブル構造解析 + 正規表現（電話番号・メール・免許番号） |
| 並行数 | 2リクエスト、3秒間隔 |

Spider種別:

| Spider | 用途 |
|--------|------|
| CompanyWebsiteSpider | 企業Webサイトから直接情報収集 |
| ZennichiFudousanSpider | 全日本不動産協会の会員検索から収集 |

**Step 2: AIスコアリング + メール生成**

| 項目 | 内容 |
|------|------|
| スコアリング基準 | 企業規模・デジタル成熟度・AI/DXニーズ推定・アプローチしやすさ |
| スコア範囲 | 0-100 |
| 出力 | スコア・根拠・推奨アプローチ・推定課題・商談ポイント |
| メール生成条件 | スコア >= min_score（デフォルト40） |
| メール内容 | 件名・本文（200-300文字）・フォローアップタイミング・フォローアップ件名 |
| サービス | AIO Insight（AI検索最適化診断・対策サービス） |
| CTA | 無料LLMO診断レポートの申し込み |

**Step 3: メール送信**

| 項目 | 内容 |
|------|------|
| 送信エンジン | Resend API |
| 形式 | HTML（プレーンテキストをHTMLエスケープ後に変換） |
| 送信間隔 | 5秒（レート制限対策） |
| 上限 | 1回あたり最大20通（max_emails_per_run） |
| Dry Runモード | --dry-run で送信をスキップし分析結果のみ出力 |

**Step 4: 結果エクスポート**

| 出力ファイル | 内容 |
|---|---|
| pipeline_result_{timestamp}.json | 全リードの処理結果 |
| pipeline_result_latest.json | 最新結果（n8n連携用） |
| hot_leads_{timestamp}.json | スコア60以上の高スコアリードのみ |

#### 2.2.4 データモデル: LeadData

| フィールド | 型 | 説明 |
|---|---|---|
| company_name | string | 企業名 |
| representative | string | 代表者名 |
| address | string | 住所 |
| phone | string | 電話番号 |
| email | string | メールアドレス |
| website | string | WebサイトURL |
| business_type | string | 事業内容 |
| area | string | 対象エリア |
| source_url | string | 収集元URL |
| scraped_at | string (ISO8601) | 収集日時 |
| license_number | string | 宅建業免許番号 |
| employee_count | string | 従業員数 |
| established | string | 設立年 |
| score | float | リードスコア（Gemini算出） |

バリデーション: company_name かつ (phone or email or website) が存在すること。

#### 2.2.5 CLIインターフェース

```
python pipeline.py --targets <file> [options]

必須:
  --targets, -t    ターゲットURLのJSONファイル（配列形式）

オプション:
  --min-score, -s  メール送信の最低スコア（デフォルト: 40）
  --dry-run, -d    メール送信しない（テスト用）
  --output, -o     出力ディレクトリ（デフォルト: ./pipeline_output）
```

---

### 2.3 design_studio/ — LP生成 & 編集UI

#### 2.3.1 概要

ストックしたデザインを参考に、Claude APIでランディングページを生成・編集するReact UIコンポーネント群。

#### 2.3.2 構成ファイル

| ファイル | 責務 |
|----------|------|
| `design_studio.jsx` | デザインDNA抽出 -> LP一括生成 |
| `lp_builder.jsx` | セクション分割編集 + ドラッグ並び替え + AI修正 |

#### 2.3.3 Design Studio（デザインDNA -> LP一括生成）

| ステップ | 処理 |
|----------|------|
| 1 | ユーザーがおしゃれなサイトのURLを1-5件入力 |
| 2 | Claude APIがデザインDNA（カラー・フォント・レイアウト）を分析 |
| 3 | 抽出したDNAを基にオリジナルLPを日本語で生成 |
| 4 | プレビュー / コード表示 / HTMLダウンロード |

#### 2.3.4 LP Builder（セクション分割編集）

| 機能 | 説明 |
|------|------|
| セクション生成 | 8種類（ヒーロー / 課題提起 / ソリューション / 機能紹介 / 実績 / 料金 / FAQ / CTA+フッター） |
| スタイル引き継ぎ | 前セクションのスタイルを自動継承して統一感を維持 |
| AI修正指示 | セクション単位で自然言語指示（例: 「背景を暗く」「CTAを大きく」） |
| ドラッグ&ドロップ | セクションの構成順序を変更 |
| セクション操作 | 複製・削除 |
| 出力 | フルプレビュー / HTML一括ダウンロード |

---

### 2.4 Supabase連携（永続化 + ベクトル検索）

#### 2.4.1 概要

デザインストックをSupabase PostgreSQL + pgvectorに永続化し、自然言語で類似デザインを検索可能にする。

#### 2.4.2 テーブル構成

| テーブル | 用途 |
|----------|------|
| design_entries | デザインストック本体（embedding列含む） |
| design_changes | 変化検知履歴 |
| trend_reports | トレンドレポート |

#### 2.4.3 ベクトル検索

| 項目 | 内容 |
|------|------|
| Embeddingモデル | Gemini gemini-embedding-001（768次元） |
| ベクトル化対象 | aesthetic + overview + industry + カラー + フォント + タグ + 特徴要素 + デザイン原則 |
| インデックス | HNSW (m=16, ef_construction=64) |
| 類似度関数 | コサイン類似度（match_designs RPC） |
| フォールバック | RPC 404時はPython側でコサイン類似度計算 |

#### 2.4.4 同期

| 方向 | コマンド |
|------|----------|
| ローカル -> Supabase | `python supabase_store.py --sync` |
| Supabase -> ローカル | `python supabase_store.py --sync-back` |
| 自動同期 | パイプライン実行時にSupabase設定があれば自動upsert |

#### 2.4.5 CLIインターフェース

```
python supabase_store.py [command]

  --init           スキーマSQL生成（supabase_schema.sql出力）
  --sync           ローカル -> Supabase同期
  --sync-back      Supabase -> ローカル同期
  --search <text>  自然言語で類似デザイン検索
  --similar-to <id>  指定IDに類似したデザイン検索
  --stats          統計表示
  --stock-dir      ストックディレクトリ指定（デフォルト: ./design_stock_v2）
```

---

## 3. 外部サービス依存

### 3.1 API一覧

| サービス | 用途 | 必須/任意 | 環境変数 | 無料枠 |
|----------|------|-----------|----------|--------|
| Google Gemini | KW生成・分析・スコアリング・メール生成・Embedding | 必須 | GEMINI_API_KEY | 1日1,500req |
| Serper.dev | Google検索結果取得 | 推奨 | SERPER_API_KEY | 永久2,500q |
| Firecrawl | デザインDNA抽出・スクリーンショット | 推奨 | FIRECRAWL_API_KEY | 500クレジット |
| Scrapling | ステルススクレイピング・フォールバック | 任意 | なし（OSS） | 無制限 |
| Resend | メール送信 | 任意 | RESEND_API_KEY | 100通/日 |
| Supabase | 永続化・ベクトル検索 | 任意 | SUPABASE_URL, SUPABASE_KEY | 500MB |
| Claude API | LP生成（React UI内） | 任意 | UI側で設定 | 使用量次第 |

### 3.2 通知連携

| サービス | 環境変数 | トリガー |
|----------|----------|----------|
| Discord Webhook | DISCORD_WEBHOOK_URL | デザイン変化検知時 / スケジューラー完了時 |
| Slack Webhook | SLACK_WEBHOOK_URL | デザイン変化検知時 / スケジューラー完了時 |

---

## 4. フロントエンド

### 4.1 Next.js アプリケーション

| 項目 | 内容 |
|------|------|
| フレームワーク | Next.js 14 (App Router) |
| ランタイム | React 18 |
| 現状 | ランディングページ（`app/page.js`）のみ |
| 言語 | ja |

### 4.2 n8nワークフロー

| ファイル | 用途 |
|----------|------|
| 01_design_research_daily.json | デザイン調査の日次自動実行 |
| 02_auto_lp_generation.json | LP自動生成ワークフロー |
| 03_lead_pipeline.json | リードパイプラインワークフロー |
| 04_aio_zero_meeting_sales.json | AIO ゼロミーティング営業ワークフロー |

---

## 5. 非機能要件

### 5.1 レート制限対策

| 対象 | 制御 |
|------|------|
| Serper API | 検索間隔0.5秒、日次15クエリ上限 |
| Firecrawl API | タイムアウト30秒 |
| Gemini API | 分析間隔1.5秒 |
| Resend API | 送信間隔5秒、1回あたり最大20通 |
| Scrapling Spider | 並行2-3リクエスト、2-3秒間隔 |
| 変化検知 | チェック間隔2秒 |

### 5.2 フォールバック戦略

| 優先 | フォールバック | 対象 |
|------|---------------|------|
| Firecrawl Branding API | Scrapling + Gemini直接分析 | デザインデータ取得 |
| Firecrawl Screenshot API | Scrapling DynamicFetcher (メタデータ保存) | スクリーンショット |
| Supabase RPC (match_designs) | Python側コサイン類似度計算 | ベクトル検索 |
| supabase パッケージ | REST API直接呼び出し | Supabase操作 |

### 5.3 セキュリティ

| 項目 | 対応 |
|------|------|
| APIキー管理 | .envファイル（.gitignore済み） |
| メール本文 | html.escape()によるXSS対策 |
| クロール礼儀 | download_delay設定、concurrent_requests制限 |
| デバッグログ | APIキーは先頭5文字のみ表示 |

### 5.4 データ永続化

| レイヤー | ストレージ | 用途 |
|----------|-----------|------|
| ローカル | design_stock_v2/ (JSON) | 高速アクセス・オフライン動作 |
| クラウド | Supabase PostgreSQL | 永続化・複数環境共有 |
| ベクトル | pgvector (768次元HNSW) | 類似デザイン検索 |

---

## 6. CLI コマンド一覧

### design_research/

```
# メインパイプライン
python design_researcher_v2.py                        # フル実行
python design_researcher_v2.py --config config.json   # 設定ファイル指定
python design_researcher_v2.py --report-only           # トレンドレポートのみ
python design_researcher_v2.py --check-changes         # 変化検知のみ
python design_researcher_v2.py --screenshot <url>      # スクリーンショットのみ

# スケジューラー
python scheduler_v2.py                                 # 常駐（デフォルト03:00）
python scheduler_v2.py --run-now                       # 即時実行
python scheduler_v2.py --setup-cron --hour 3           # cron設定出力
python scheduler_v2.py --setup-systemd --hour 3        # systemd設定生成

# 変化検知
python design_monitor.py --check                       # 全サイトチェック
python design_monitor.py --screenshot <url>            # スクリーンショット
python design_monitor.py --max-checks 20               # チェック上限指定

# Supabase
python supabase_store.py --init                        # スキーマSQL生成
python supabase_store.py --sync                        # ローカル -> Supabase
python supabase_store.py --sync-back                   # Supabase -> ローカル
python supabase_store.py --search "ミニマル ダーク"     # 類似検索
python supabase_store.py --similar-to <id>             # 類似エントリ検索
python supabase_store.py --stats                       # 統計表示
```

### lead_scraper/

```
python pipeline.py --targets targets.json              # 本番実行
python pipeline.py --targets targets.json --dry-run    # テスト（送信なし）
python pipeline.py --targets targets.json --min-score 60  # スコア閾値変更
python pipeline.py --targets targets.json --output ./out  # 出力先変更
```

---

## 7. 環境構築

### 7.1 依存パッケージ

```
# Python (requirements.txt)
google-genai>=1.0.0        # Gemini API
requests>=2.31.0           # HTTP通信
python-dotenv>=1.0.0       # .env読み込み
scrapling[all]>=0.4.0      # Webスクレイピング
resend>=2.0.0              # メール送信
supabase>=2.0.0            # Supabase連携

# Node.js (package.json)
next ^14.2.0               # Next.js フレームワーク
react ^18.2.0              # React
n8n ^1.62.0                # ワークフロー自動化（devDependencies）
```

### 7.2 セットアップ手順

```bash
# 1. Python依存インストール
pip install -r requirements.txt
scrapling install

# 2. 環境変数設定
cp .env.example .env
# .env を編集してAPIキーを設定

# 3. デザイン調査テスト
cd design_research
python design_researcher_v2.py

# 4. リードパイプラインテスト
cd lead_scraper
python pipeline.py --targets targets_sample.json --dry-run

# 5. (任意) Supabaseセットアップ
cd design_research
python supabase_store.py --init
# 出力されたSQLをSupabase SQL Editorで実行
python supabase_store.py --sync
```
