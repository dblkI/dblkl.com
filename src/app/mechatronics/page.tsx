import Header from '@/components/Header';
import BackNav from '@/components/BackNav';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Ingeniería | DBLKL',
    description: 'Proyectos de ingeniería y mecatrónica.',
};

export default function Mechatronics() {
    return (
        <div className="subpage-layout fade-in">
            <BackNav />
            <Header tagline="Proyectos & Desarrollo" mainText="INGENIERÍA" />
            <section className="content-body">
                <p className="description">Sección en construcción para mostrar mis proyectos de ingeniería.</p>
            </section>
        </div>
    );
}
