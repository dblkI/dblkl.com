import Link from 'next/link';

export default function BackNav() {
    return (
        <nav className="back-nav">
            <Link href="/" className="back-link">
                ← VOLVER AL INICIO
            </Link>
        </nav>
    );
}
