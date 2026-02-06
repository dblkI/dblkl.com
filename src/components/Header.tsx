export default function Header({ tagline, mainText, accentText }: { tagline: string, mainText: string, accentText?: string }) {
    return (
        <header>
            <p className="tagline">{tagline}</p>
            <h1 className="brand">
                {mainText} {accentText && <span className="accent">{accentText}</span>}
            </h1>
        </header>
    );
}
