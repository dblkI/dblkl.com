import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Daniel Blanquel | Home',
  description: 'Portafolio de proyectos, fotografía y prototipado.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>
        <div className="noise-overlay"></div>
        {children}
      </body>
    </html>
  );
}
