"""
LeadGenius AI - リード収集Spider
関西エリアの不動産会社情報を公開ソースから自動収集する

使用方法:
    pip install "scrapling[all]"
    scrapling install
    python lead_spider.py
"""

import json
import re
import asyncio
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from scrapling.spiders import Spider, Request, Response
from scrapling.fetchers import Fetcher


# =============================================================================
# データモデル
# =============================================================================

@dataclass
class LeadData:
    """リード候補の企業データ"""
    company_name: str = ""
    representative: str = ""          # 代表者名
    address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    business_type: str = ""           # 事業内容（売買/賃貸/管理 等）
    area: str = ""                    # 対象エリア
    source_url: str = ""              # 収集元URL
    scraped_at: str = ""              # 収集日時
    license_number: str = ""          # 宅建業免許番号
    employee_count: str = ""          # 従業員数
    established: str = ""             # 設立年
    score: float = 0.0                # リードスコア（後でGemini APIで算出）

    def is_valid(self) -> bool:
        """最低限の情報があるかチェック"""
        return bool(self.company_name and (self.phone or self.email or self.website))

    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# ユーティリティ関数
# =============================================================================

def extract_phone(text: str) -> list[str]:
    """テキストから日本の電話番号を抽出"""
    patterns = [
        r'0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}',  # 固定電話
        r'0[789]0[-\s]?\d{4}[-\s]?\d{4}',          # 携帯電話
        r'0120[-\s]?\d{3}[-\s]?\d{3}',             # フリーダイヤル
    ]
    phones = []
    for pattern in patterns:
        phones.extend(re.findall(pattern, text))
    return list(set(phones))


def extract_email(text: str) -> list[str]:
    """テキストからメールアドレスを抽出"""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(pattern, text)
    # 画像ファイル等のfalse positiveを除外
    return [e for e in emails if not e.endswith(('.png', '.jpg', '.gif', '.svg'))]


def extract_license_number(text: str) -> str:
    """宅建業免許番号を抽出"""
    patterns = [
        r'(?:国土交通大臣|[^\s]{2,4}知事)\s*[\(（]\s*\d+\s*[\)）]\s*第?\s*\d+\s*号?',
        r'宅地建物取引業[者]?\s*免許\s*[\(（]?\s*(?:国土交通大臣|[^\s]{2,4}知事)\s*[\(（]\s*\d+\s*[\)）]',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return ""


def clean_text(text: str) -> str:
    """テキストのクリーニング"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


# =============================================================================
# ソース1: 全日本不動産協会 会員検索（公開データ）
# =============================================================================

class ZennichiFudousanSpider(Spider):
    """
    全日本不動産協会の会員検索結果からリード情報を収集
    注意: 実際のURL・セレクタは対象サイトに合わせて調整が必要
    """
    name = "zennichi_fudousan"
    concurrent_requests = 3           # 礼儀正しいクロール
    download_delay = 2.0              # 2秒間隔
    
    # 関西エリアの都道府県コード（例）
    KANSAI_PREFECTURES = {
        "osaka": "27",
        "kyoto": "26",
        "hyogo": "28",
        "nara": "29",
        "shiga": "25",
        "wakayama": "30",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.leads: list[LeadData] = []

    @property
    def start_urls(self):
        """関西各府県の検索URLを生成"""
        # ※ 実際のURLは対象サイトの構造に合わせて変更してください
        base_url = "https://www.zennichi.or.jp/member/search"
        urls = []
        for pref_name, pref_code in self.KANSAI_PREFECTURES.items():
            urls.append(f"{base_url}?prefecture={pref_code}&category=sale")
        return urls

    async def parse(self, response: Response):
        """検索結果一覧ページの解析"""
        # 各企業カードを取得
        companies = response.css('.member-card, .search-result-item, tr.member-row')
        
        for company in companies:
            lead = LeadData(
                source_url=str(response.url),
                scraped_at=datetime.now().isoformat(),
                area="関西",
            )
            
            # 企業名
            lead.company_name = clean_text(
                company.css('.company-name::text, .name a::text, td.company::text').get("")
            )
            
            # 詳細ページへのリンクがあればフォロー
            detail_link = company.css('a.detail-link, .company-name a')
            if detail_link:
                href = detail_link[0].attrib.get('href', '')
                if href:
                    yield response.follow(
                        href,
                        callback=self.parse_detail,
                        cb_kwargs={"lead": lead}
                    )
            else:
                # 一覧ページから直接情報を取得
                self._extract_from_card(company, lead)
                if lead.is_valid():
                    self.leads.append(lead)
                    yield lead.to_dict()

        # ページネーション
        next_page = response.css('a.next, .pagination .next a, a[rel="next"]')
        if next_page:
            href = next_page[0].attrib.get('href', '')
            if href:
                yield response.follow(href)

    async def parse_detail(self, response: Response, lead: LeadData):
        """企業詳細ページの解析"""
        page_text = response.css('body').get("")
        
        # 代表者名
        lead.representative = clean_text(
            response.css(
                '.representative::text, '
                'th:contains("代表者") + td::text, '
                'dt:contains("代表") + dd::text'
            ).get("")
        )
        
        # 住所
        lead.address = clean_text(
            response.css(
                '.address::text, '
                'th:contains("所在地") + td::text, '
                'th:contains("住所") + td::text'
            ).get("")
        )
        
        # 電話番号
        phone_text = response.css(
            '.phone::text, '
            'th:contains("電話") + td::text, '
            'th:contains("TEL") + td::text'
        ).get("")
        if phone_text:
            lead.phone = clean_text(phone_text)
        else:
            phones = extract_phone(page_text)
            if phones:
                lead.phone = phones[0]
        
        # メールアドレス
        email_el = response.css('a[href^="mailto:"]')
        if email_el:
            lead.email = email_el[0].attrib.get('href', '').replace('mailto:', '')
        else:
            emails = extract_email(page_text)
            if emails:
                lead.email = emails[0]
        
        # ウェブサイト
        website_el = response.css(
            'th:contains("ホームページ") + td a, '
            'th:contains("URL") + td a, '
            'a.website-link'
        )
        if website_el:
            lead.website = website_el[0].attrib.get('href', '')
        
        # 免許番号
        lead.license_number = extract_license_number(page_text)
        
        # 事業内容
        lead.business_type = clean_text(
            response.css(
                'th:contains("業務内容") + td::text, '
                'th:contains("取扱業務") + td::text'
            ).get("")
        )
        
        if lead.is_valid():
            self.leads.append(lead)
            yield lead.to_dict()


# =============================================================================
# ソース2: 企業Webサイトからの直接収集
# =============================================================================

class CompanyWebsiteSpider(Spider):
    """
    企業のWebサイトから直接情報を収集する
    ターゲットリストのURLを入力として使用
    """
    name = "company_website"
    concurrent_requests = 2
    download_delay = 3.0
    
    def __init__(self, target_urls: list[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._target_urls = target_urls or []
        self.leads: list[LeadData] = []

    @property
    def start_urls(self):
        return self._target_urls

    async def parse(self, response: Response):
        """企業サイトのトップページを解析"""
        lead = LeadData(
            source_url=str(response.url),
            website=str(response.url),
            scraped_at=datetime.now().isoformat(),
            area="関西",
        )

        try:
            page_text = response.css('body').get("")
        except (UnicodeDecodeError, Exception):
            # Shift-JIS等のエンコーディング対策
            try:
                raw = response.css('body')
                page_text = raw._root.text_content() if raw else ""
            except Exception:
                page_text = ""

        # タイトルから企業名を推定
        try:
            title = response.css('title::text').get("")
        except (UnicodeDecodeError, Exception):
            title = ""
        lead.company_name = self._extract_company_name(title, response)

        # 電話番号
        phones = extract_phone(page_text)
        if phones:
            lead.phone = phones[0]

        # メールアドレス
        try:
            email_links = response.css('a[href^="mailto:"]')
        except Exception:
            email_links = []
        if email_links:
            lead.email = email_links[0].attrib.get('href', '').replace('mailto:', '')
        else:
            emails = extract_email(page_text)
            if emails:
                lead.email = emails[0]

        # 会社概要ページを探してフォロー
        try:
            about_links = response.css(
                'a[href*="company"], a[href*="about"], '
                'a[href*="gaiyou"], a[href*="profile"], '
                'a[href*="corporate"]'
            )
        except Exception:
            about_links = []

        # テキストで「会社概要」リンクを探す
        if not about_links:
            try:
                about_links = response.find_by_text('会社概要')
                about_links = [a for a in about_links if a.tag == 'a'] if about_links else []
            except Exception:
                about_links = []
        if not about_links:
            try:
                about_links = response.find_by_text('企業情報')
                about_links = [a for a in about_links if a.tag == 'a'] if about_links else []
            except Exception:
                about_links = []

        if about_links:
            href = about_links[0].attrib.get('href', '')
            if href:
                yield response.follow(
                    href,
                    callback=self.parse_company_page,
                    cb_kwargs={"lead": lead}
                )
                return

        # 会社概要ページが見つからない場合はトップページから収集
        self._extract_from_page(response, lead, page_text)
        if lead.is_valid():
            self.leads.append(lead)
            yield lead.to_dict()

    async def parse_company_page(self, response: Response, lead: LeadData):
        """会社概要ページの解析"""
        try:
            page_text = response.css('body').get("")
        except (UnicodeDecodeError, Exception):
            try:
                raw = response.css('body')
                page_text = raw._root.text_content() if raw else ""
            except Exception:
                page_text = ""
        self._extract_from_page(response, lead, page_text)
        
        if lead.is_valid():
            self.leads.append(lead)
            yield lead.to_dict()

    def _extract_company_name(self, title: str, response: Response) -> str:
        """タイトルやOGPから企業名を抽出"""
        # OGP
        og_name = response.css('meta[property="og:site_name"]')
        if og_name:
            return clean_text(og_name[0].attrib.get('content', ''))
        
        # titleタグをクリーニング
        if title:
            # 「| ホーム」「- トップ」等を除去
            name = re.split(r'[|\-–—]', title)[0]
            name = re.sub(r'(株式会社|有限会社|合同会社)', r' \1 ', name)
            return clean_text(name)
        return ""

    def _extract_from_page(self, response: Response, lead: LeadData, page_text: str):
        """ページから詳細情報を抽出"""
        
        # テーブル形式（会社概要ページでよくある形式）
        rows = response.css('table tr, dl')
        for row in rows:
            header = clean_text(row.css('th::text, dt::text').get(""))
            value = clean_text(row.css('td::text, dd::text').get(""))
            
            if not header or not value:
                continue
            
            if any(k in header for k in ['会社名', '商号', '社名', '名称']):
                if not lead.company_name:
                    lead.company_name = value
            elif any(k in header for k in ['代表', '代表者', '代表取締役']):
                lead.representative = value
            elif any(k in header for k in ['所在地', '住所', '本社']):
                lead.address = value
            elif any(k in header for k in ['電話', 'TEL', 'Tel']):
                lead.phone = value
            elif any(k in header for k in ['メール', 'E-mail', 'Email', 'email']):
                lead.email = value
            elif any(k in header for k in ['設立', '創業', '創立']):
                lead.established = value
            elif any(k in header for k in ['従業員', '社員']):
                lead.employee_count = value
            elif any(k in header for k in ['免許', '登録', '許可']):
                lead.license_number = value
            elif any(k in header for k in ['事業', '業務', '取扱']):
                lead.business_type = value
        
        # テーブルから取れなかった情報をフォールバック
        if not lead.phone:
            phones = extract_phone(page_text)
            if phones:
                lead.phone = phones[0]
        
        if not lead.email:
            email_links = response.css('a[href^="mailto:"]')
            if email_links:
                lead.email = email_links[0].attrib.get('href', '').replace('mailto:', '')
        
        if not lead.license_number:
            lead.license_number = extract_license_number(page_text)


# =============================================================================
# リードデータ管理
# =============================================================================

class LeadManager:
    """収集したリードデータの管理・エクスポート"""
    
    def __init__(self, output_dir: str = "./leads_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.leads: list[LeadData] = []
    
    def add_leads(self, leads: list[LeadData]):
        """リードを追加（重複チェック付き）"""
        existing = {(l.company_name, l.phone) for l in self.leads}
        for lead in leads:
            key = (lead.company_name, lead.phone)
            if key not in existing:
                self.leads.append(lead)
                existing.add(key)
    
    def export_json(self, filename: str = None) -> str:
        """JSON形式でエクスポート"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"leads_{timestamp}.json"
        
        filepath = self.output_dir / filename
        data = {
            "exported_at": datetime.now().isoformat(),
            "total_leads": len(self.leads),
            "leads": [lead.to_dict() for lead in self.leads]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {len(self.leads)}件のリードを {filepath} にエクスポートしました")
        return str(filepath)
    
    def export_csv(self, filename: str = None) -> str:
        """CSV形式でエクスポート（Gemini APIへの入力用）"""
        import csv
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"leads_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        if not self.leads:
            print("⚠️ エクスポートするリードがありません")
            return ""
        
        fieldnames = list(asdict(self.leads[0]).keys())
        
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for lead in self.leads:
                writer.writerow(lead.to_dict())
        
        print(f"✅ {len(self.leads)}件のリードを {filepath} にエクスポートしました")
        return str(filepath)
    
    def print_summary(self):
        """収集結果のサマリーを表示"""
        total = len(self.leads)
        with_email = sum(1 for l in self.leads if l.email)
        with_phone = sum(1 for l in self.leads if l.phone)
        with_website = sum(1 for l in self.leads if l.website)
        with_representative = sum(1 for l in self.leads if l.representative)
        
        print("\n" + "=" * 60)
        print("📊 LeadGenius AI - リード収集結果サマリー")
        print("=" * 60)
        print(f"  総リード数:     {total}")
        print(f"  メール取得済:   {with_email} ({with_email/total*100:.0f}%)" if total else "")
        print(f"  電話取得済:     {with_phone} ({with_phone/total*100:.0f}%)" if total else "")
        print(f"  Web取得済:      {with_website} ({with_website/total*100:.0f}%)" if total else "")
        print(f"  代表者名取得:   {with_representative} ({with_representative/total*100:.0f}%)" if total else "")
        print("=" * 60)


# =============================================================================
# メイン実行
# =============================================================================

def run_company_scraper(target_urls: list[str]):
    """
    企業Webサイトからリード情報を収集する
    
    Args:
        target_urls: 収集対象の企業WebサイトURLリスト
    """
    print("🚀 LeadGenius AI - 企業Webサイトスクレイピング開始")
    print(f"   対象: {len(target_urls)}社")
    
    spider = CompanyWebsiteSpider(target_urls=target_urls)
    result = spider.start()
    
    manager = LeadManager()
    manager.add_leads(spider.leads)
    manager.print_summary()
    manager.export_json()
    manager.export_csv()
    
    return manager


def run_association_scraper():
    """不動産協会の会員検索からリードを収集する"""
    print("🚀 LeadGenius AI - 不動産協会会員スクレイピング開始")
    
    spider = ZennichiFudousanSpider()
    result = spider.start()
    
    manager = LeadManager()
    manager.add_leads(spider.leads)
    manager.print_summary()
    manager.export_json()
    manager.export_csv()
    
    return manager


# =============================================================================
# 使用例
# =============================================================================

if __name__ == "__main__":
    # 例: 関西の不動産会社のWebサイトリスト
    # 実際の使用時はここにターゲットリストのURLを入れる
    sample_targets = [
        # "https://www.example-realestate-osaka.co.jp",
        # "https://www.example-fudousan-kobe.com",
        # "https://www.example-jutaku-kyoto.co.jp",
    ]
    
    if sample_targets:
        manager = run_company_scraper(sample_targets)
    else:
        print("=" * 60)
        print("LeadGenius AI - リード収集Spider")
        print("=" * 60)
        print()
        print("使い方:")
        print("  1. sample_targets リストに対象企業のURLを追加")
        print("  2. python lead_spider.py を実行")
        print()
        print("  または、他のスクリプトからインポートして使用:")
        print()
        print('  from lead_spider import run_company_scraper')
        print('  manager = run_company_scraper(["https://example.com"])')
        print()
        print("--- デモ: 単一ページからの情報抽出テスト ---")
        print()
        
        # デモ: Fetcherを使った単体テスト
        try:
            page = Fetcher.get(
                'https://quotes.toscrape.com/',
                stealthy_headers=True
            )
            quotes = page.css('.quote .text::text').getall()[:3]
            print(f"✅ Scrapling動作確認OK - {len(quotes)}件取得")
            for q in quotes:
                print(f"   {q[:50]}...")
        except Exception as e:
            print(f"⚠️  Scrapling動作確認: {e}")
            print("   pip install 'scrapling[all]' && scrapling install を実行してください")
