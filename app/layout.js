export const metadata = {
  title: 'LeadGenius Design Suite',
  description: 'AI-powered design research, LP generation, and lead pipeline toolkit',
};

export default function RootLayout({ children }) {
  return (
    <html lang="ja">
      <body style={{ margin: 0, fontFamily: 'system-ui, sans-serif' }}>
        {children}
      </body>
    </html>
  );
}
