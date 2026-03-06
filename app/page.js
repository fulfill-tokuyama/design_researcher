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
        background: 'linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%)',
        color: '#e8e8f4',
      }}
    >
      <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>
        LeadGenius Design Suite
      </h1>
      <p style={{ color: '#7878a0', marginBottom: '2rem',
        textAlign: 'center', maxWidth: '480px' }}>
        Fulfill株式会社のAIサービス群を支える
        リード収集 + デザイン自動調査 + LP生成の統合ツールキット
      </p>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap',
        justifyContent: 'center' }}>
        <a
          href="https://github.com/fulfill-tokuyama/design_researcher"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            padding: '12px 24px',
            background: 'rgba(249, 115, 22, 0.2)',
            border: '1px solid #f97316',
            borderRadius: '8px',
            color: '#f97316',
            textDecoration: 'none',
            fontWeight: 600,
          }}
        >
          GitHub
        </a>
      </div>
    </main>
  );
}
