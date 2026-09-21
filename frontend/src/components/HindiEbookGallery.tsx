import Link from "next/link";

export type HindiEbookItem = {
  id: string;
  title: string;
  subtitle: string;
  cover: string;
};

type Props = {
  books: HindiEbookItem[];
};

export default function HindiEbookGallery({ books }: Props) {
  return (
    <div className="hp-ebook-grid">
      {books.map((book) => (
        <Link
          key={book.id}
          href={`/hindi/ebooks/${book.id}`}
          className="hp-ebook-card"
        >
          <div className="hp-ebook-cover">
            <img src={book.cover} alt={book.title} />
          </div>
          <div className="hp-ebook-meta">
            <h2>{book.title}</h2>
            <p>{book.subtitle}</p>
            <span className="hp-btn hp-btn-yellow hp-ebook-open">
              किताब खोलें (Open Book)
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}
