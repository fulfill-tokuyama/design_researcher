const C = {
  bg: '#0a0a0f',
  tx: '#e8e8f4',
  mt: '#7878a0',
  ac: '#f97316',
  bd: '#222238',
};

const tools = [
  {
    href: '/aio',
    title: 'AIO Insight',
    desc: 'AI検索最適化（LLMO/AIO）サービスのランディングページ',
    icon: '🤖',
  },
  {
    href: '/studio',
    title: 'Design Studio',
    desc: '参考サイトのURLからデザインDNAを抽出し、AIでLPを一括生成',
    icon: '🎨',
  },
  {
    href: '/builder',
    title: 'LP Builder',
    desc: 'セクション分割でLPを編集。ドラッグ並び替え・AI修正指示に対応',
    icon: '🏗️',
  },
];

export default function Home() {
  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
        background: `linear-gradient(135deg, ${C.bg} 0%, #1a1a2e 100%)`,
        color: C.tx,
      }}
    >
      <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>
        LeadGenius Design Suite
      </h1>
      <p
        style={{
          color: C.mt,
          marginBottom: '2.5rem',
          textAlign: 'center',
          maxWidth: '480px',
          lineHeight: 1.7,
        }}
      >
        Fulfill株式会社のAIサービス群を支える
        リード収集 + デザイン自動調査 + LP生成の統合ツールキット
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1rem',
          maxWidth: '640px',
          width: '100%',
          marginBottom: '2rem',
        }}
      >
        {tools.map((t) => (
          <a
            key={t.href}
            href={t.href}
            style={{
              padding: '24px',
              background: 'rgba(255,255,255,0.03)',
              border: `1px solid ${C.bd}`,
              borderRadius: '12px',
              color: C.tx,
              textDecoration: 'none',
              transition: 'border-color 0.2s',
            }}
          >
            <div style={{ fontSize: '2rem', marginBottom: '8px' }}>{t.icon}</div>
            <div
              style={{
                fontSize: '1.1rem',
                fontWeight: 700,
                marginBottom: '6px',
                color: C.ac,
              }}
            >
              {t.title}
            </div>
            <div style={{ fontSize: '0.85rem', color: C.mt, lineHeight: 1.6 }}>
              {t.desc}
            </div>
          </a>
        ))}
      </div>

      <a
        href="https://github.com/fulfill-tokuyama/design_researcher"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          padding: '10px 20px',
          background: 'rgba(249, 115, 22, 0.15)',
          border: `1px solid ${C.ac}`,
          borderRadius: '8px',
          color: C.ac,
          textDecoration: 'none',
          fontWeight: 600,
          fontSize: '0.9rem',
        }}
      >
        GitHub
      </a>
    </main>
  );
}
