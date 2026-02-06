import Link from 'next/link';

export default function MainNav() {
    return (
        <nav className="main-nav">
            <Link href="/mechatronics" className="nav-item">
                <span className="number">01</span><span className="label">Ingeniería</span>
            </Link>
            <Link href="/photography" className="nav-item">
                <span className="number">02</span><span className="label">Fotografía</span>
            </Link>
            <Link href="/3d-printing" className="nav-item">
                <span className="number">03</span><span className="label">Prototipado</span>
            </Link>
        </nav>
    );
}
