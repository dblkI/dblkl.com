import Header from '@/components/Header';
import BackNav from '@/components/BackNav';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Prototipado | DBLKL',
    description: 'Diseño 3D y manufactura aditiva.',
};

export default function Printing() {
    return (
        <div className="subpage-layout fade-in">
            <BackNav />
            <Header tagline="Manufactura Digital" mainText="3D PRINTING" />
            <section className="content-body">
                <p className="description">Sección en construcción para mostrar mis modelos y prototipos 3D.</p>
            </section>
        </div>
    );
}
