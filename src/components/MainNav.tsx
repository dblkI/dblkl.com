import Link from 'next/link';

export default function MainNav() {
    return (
        <nav className="main-nav">
            <Link href="/projects" className="nav-item">
                <span className="number">01</span><span className="label">Proyectos</span>
            </Link>
            <Link href="/photography" className="nav-item">
                <span className="number">02</span><span className="label">Fotografía</span>
            </Link>
        </nav>
    );
}
