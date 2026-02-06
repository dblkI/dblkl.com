import Link from 'next/link';

export default function Footer() {
  return (
    <footer className="fade-in-delayed">
        <div className="social-links">
            <a href="https://www.linkedin.com/in/dblanquel/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
            <a href="https://www.instagram.com/dblkl.archive/" target="_blank" rel="noopener noreferrer">Instagram</a>
            <a href="https://vs.co/wjgwejki" target="_blank" rel="noopener noreferrer">VSCO</a>
            <a href="mailto:hola@dblkl.com" className="email-link">hola@dblkl.com</a>
        </div>
        <p className="location">Basado en México</p>
    </footer>
  );
}
