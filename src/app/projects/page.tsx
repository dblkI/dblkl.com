import Header from '@/components/Header';
import BackNav from '@/components/BackNav';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
    title: 'Proyectos | DBLKL',
    description: 'Proyectos, desarrollo y prototipado.',
};

export default function Projects() {
    return (
        <div className="subpage-layout fade-in">
            <BackNav />
            <Header tagline="Proyectos & Desarrollo" mainText="PROYECTOS" />
            <section className="content-body">
                <div className="projects-grid">
                    <Link href="/3d-printing" className="project-card">
                        <h3>Prototipado 3D</h3>
                        <p>Diseño e impresión de piezas.</p>
                    </Link>
                    <Link href="/pdf-to-epub" className="project-card">
                        <h3>PDF a EPUB</h3>
                        <p>Conversión optimizada de formatos de lectura.</p>
                    </Link>
                </div>
            </section>
        </div>
    );
}
