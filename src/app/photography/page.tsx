import Header from '@/components/Header';
import BackNav from '@/components/BackNav';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Fotografía | DBLKL',
    description: 'Portafolio de fotografía y arquitectura.',
};

export default function Photography() {
    return (
        <div className="subpage-layout fade-in">
            <BackNav />
            <Header tagline="Archivo Visual" mainText="FOTOGRAFÍA" />
            <section className="content-body">
                <p className="description">Sección en construcción para mostrar mi portafolio de arquitectura y texturas desaturadas.</p>
            </section>
        </div>
    );
}
