import Header from '@/components/Header';
import MainNav from '@/components/MainNav';
import Footer from '@/components/Footer';

export default function Home() {
  return (
    <main className="hero fade-in">
      <Header tagline="HELLO WORLD" mainText="DANIEL" accentText="BLANQUEL" />
      <MainNav />
      <Footer />
    </main>
  );
}
