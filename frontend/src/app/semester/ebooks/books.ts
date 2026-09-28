export type SemesterBook = {
  id: string;
  subject: string;
  entry: string;
};

export type SemesterGroup = {
  id: string;
  label: string;
  books: SemesterBook[];
};

export type SemesterClass = {
  id: string;
  label: string;
  semesters: SemesterGroup[];
};

export const SEMESTER_CLASSES: SemesterClass[] = [
  {
    id: "1",
    label: "Class 1",
    semesters: [
      {
        id: "1",
        label: "Semester 1",
        books: [
          { id: "01", subject: "Computer", entry: "flipbook.html" },
          { id: "02", subject: "General Knowledge", entry: "index.html" },
          { id: "03", subject: "Mathematics", entry: "index.html" },
          { id: "04", subject: "English", entry: "index.html" },
          { id: "05", subject: "Environmental Studies", entry: "index.html" },
        ],
      },
    ],
  },
];

export function findSemesterBook(id: string) {
  for (const cls of SEMESTER_CLASSES) {
    for (const sem of cls.semesters) {
      const book = sem.books.find((b) => b.id === id);
      if (book) return { cls, sem, book };
    }
  }
  return null;
}
